# 05 — Learnings

Bugs we hit, misconceptions we corrected, and things that surprised us.
Skim this before debugging weird behavior — odds are it's already here.

---

## L1 — Per-package idempotency reporting (the big one)

**Date:** 2026-05-02
**Severity:** Output-correctness bug; agent was lying about what it did.

**Symptom:** Prompt `"install htop, tree, ncdu, and fail2ban"` against a
host where `htop` was already installed. Agent reported:

```
Newly installed: htop, tree, ncdu, fail2ban    ← wrong
Already present: none
```

But `apt history` on the VPS showed only `tree, ncdu, fail2ban` were actually
installed. `htop` was correctly skipped at the OS level.

**Root cause:** Claude wrote a single Ansible task installing all four
packages as a list:

```yaml
- name: Install packages
  apt:
    name: [htop, tree, ncdu, fail2ban]
    state: present
```

Ansible's `apt` module reports the entire task as `changed` if *any* one
package needed installing. There's no per-item breakdown at the task level.
Our parser saw "task changed" and bucketed all four packages as newly
installed.

**Fix:** updated `SYSTEM_PROMPT` in `agent/core.py` (commit `1648f02`) to
mandate one task per package:

```yaml
- name: Install htop
  apt: { name: htop, state: present }
- name: Install tree
  apt: { name: tree, state: present }
…
```

Now Ansible reports each task independently, parser buckets accurately.

**Verification:** re-ran with `"install htop, tree, cowsay, and figlet"`
where htop+tree were pre-installed and cowsay+figlet weren't. Got:

```
Newly installed: cowsay, figlet      ✓
Already present: htop, tree          ✓
Failed:          none
```

**Tradeoff:** larger playbooks for big package lists. Negligible at current
scale; revisit with a `loop`+`register` pattern if doing 100-package sweeps.

---

## L2 — `VPS_HOST=ip:port` doesn't work

**Symptom:** `ansible_host: 1.2.3.4:6689` produced
`SSH could not resolve hostname 103.20.213.145:6689`.

**Cause:** SSH's hostname field cannot contain a port. Port is a separate
parameter at the protocol level.

**Fix:** added `VPS_PORT` env var, separate `ansible_port` line in
inventory, `default(22, true)` for hosts on the standard port.

**Filed under:** "obvious in hindsight, easy to do wrong if you've never
hand-written an Ansible inventory."

---

## L3 — The non-standard port wasn't actually a non-standard port

**Symptom:** After fixing L2, agent still failed with
`SSH connection ... timed out during banner exchange`.

**Cause:** Operator believed the VPS used port 6689 for SSH (probably from
their VPS provider's panel showing some other service). Actual `sshd_config`
on the VPS had no `Port` directive, so it was on the default 22. Port 6689
had something else listening that wasn't sshd.

**Fix:** `VPS_PORT=22`. Worked immediately.

**Lesson for the runbook:** when in doubt, run on the VPS:
```bash
sudo ss -tlnp | grep ssh    # what's sshd actually bound to?
grep -E '^\s*Port' /etc/ssh/sshd_config    # explicit port directive?
```
Both give a definitive answer.

---

## L4 — "I need to log out so the agent can log in"

**Misconception:** Operator thought their existing SSH session to the VPS
would block the agent's connection.

**Truth:** SSH supports many concurrent sessions to the same host. The
agent opens its own session, runs the playbook, disconnects. Has zero
interaction with any other session you have open. Linux is multi-user by
design.

**Why this is worth noting:** It's a common mental model from
single-session systems (Windows RDP without "multiple sessions enabled",
old single-user Unix). Important to reassure operators they don't need to
log out before running the agent.

---

## L5 — Notepad on Windows can save `.env` as `.env.txt`

**Symptom:** Operator edited `.env` in Notepad, agent still read old values.

**Cause:** Notepad's "Save As" defaults to `.txt` and silently appends the
extension. The actual file on disk became `.env.txt`; the original `.env`
remained untouched.

**Fix:** in PowerShell, `dir .env*` reveals it. Rename:
```powershell
ren .env.txt .env
```

**Long-term fix:** runbook tells operators to use VS Code or Notepad++ on
Windows, where "Save As" with no extension actually means no extension.

---

## L6 — Claude does NOT "listen" to anything

**Misconception:** Question "can Claude listen to WhatsApp?"

**Truth:** Claude is a stateless API. It does not subscribe to events or
sit waiting. Architecture is always:

```
incoming event → YOUR server (which YOU build) → call Claude API → reply
```

Claude is a brain you call when needed. You build the ears (webhook
listener) and the mouth (response sender).

**Why this matters for design:** Any "bot" version (WhatsApp, Slack,
Discord) requires an always-on server running a webhook. That server is
NOT the operator's laptop — it's a separate machine (a VPS, WIPL's own
infra). The agent code becomes a function that the bot server calls; the
agent itself is unchanged.

---

## L7 — Pre-installed packages on the test VPS

**Quirk:** The Ubuntu 24.04 VPS we tested against came with a lot of
"normal dev tools" already present. Initial state survey:

| Already present | Missing |
|---|---|
| `python3.12`, `python3-pip`, `python3.12-venv` | `tree`, `ncdu`, `cowsay`, `figlet` |
| `node` (v24.15.0), `npm` | `lolcat`, `neofetch`, `sl` |
| `htop`, `jq`, `tmux` | `fail2ban` (initially) |
| `ufw` (installed but inactive) | — |
| `git`, `curl`, `openssh-server` | — |

**Implication:** any "test the agent" prompt needs a fresh-eye check of
what's actually missing. Use:
```bash
dpkg -l <pkg> | grep -q "^ii" && echo "INSTALLED" || echo "missing"
```
not `which <pkg>` — some packages ship binaries with different names
(e.g., `fail2ban` package → `fail2ban-client` binary, no `fail2ban` in
PATH; `which fail2ban` falsely reports missing).

---

## L8 — "Claude configuration file not found" warnings

**Symptom:** Every run printed:
```
Claude configuration file not found at: /root/.claude.json
A backup file exists at: /root/.claude/backups/.claude.json.backup.…
```
…three times.

**Cause:** The bundled Claude Code CLI inside the container looks for an
OAuth config file. We don't use it (we authenticate with `ANTHROPIC_API_KEY`).
The CLI complains anyway on each subprocess invocation.

**Fix (commit `5b416cc`):** `Dockerfile` pre-creates the file:
```dockerfile
RUN echo '{}' > /root/.claude.json
```
File exists → CLI doesn't complain. Auth still uses the env var.

---

## L9 — Image vs container confusion

**Symptom:** Operator ran `docker compose build`, saw the build succeed,
then ran `docker ps -a` and didn't see the agent in the container list.
Asked "where is the ansible container?"

**Truth:** An **image** is a recipe. A **container** is a running instance
of that recipe. `build` produces an image; only `run` produces a container.

The agent is **ephemeral**: spins up, does the work, exits. The `--rm` flag
auto-removes it. So `docker ps -a` shows long-running services (postgres,
n8n, etc.) but NOT the agent — which is correct behavior.

To confirm the image exists: `docker images | grep claude-vps-agent`.

---

## L10 — `ls` doesn't work in CMD

Trivial but trips Linux-fluent users on Windows. Use `dir` in CMD, or open
PowerShell where `ls` is aliased to `Get-ChildItem`.
