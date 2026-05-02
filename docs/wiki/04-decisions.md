# 04 — Decisions

Architecture decision records. Each one captures: what we chose, what we
considered, and why. Read these before changing the architecture so you
don't unwind a deliberate constraint by accident.

---

## D1 — Use Claude Agent SDK + Ansible (not Claude + raw SSH/bash)

**Date:** 2026-05-02

**Considered:**
- (a) Claude Agent SDK with custom `ssh_exec` tool calling raw bash
- (b) Claude generates Ansible playbooks; Ansible executes
- (c) Claude generates SaltStack / Chef / Puppet manifests
- (d) Computer-use / RDP automation for GUI installers

**Chose:** (b)

**Why:**
- **Idempotency for free.** Ansible's modules report `changed`/`ok` per task,
  which makes "already installed" detection trivial. Re-running is safe.
- **Cross-platform module coverage.** Ansible has 20 years of modules for
  every package manager (`apt`, `dnf`, `apk`, `pacman`, `win_chocolatey`).
  We are not rebuilding that.
- **Connection abstraction.** SSH for Linux, WinRM for Windows — same YAML
  syntax, Ansible handles the transport.
- **Auditable artifacts.** Every playbook is a YAML file we can save, diff,
  re-run.

**Why not alternatives:**
- (a) Raw bash via Claude works but loses idempotency and cross-platform
  uniformity. Claude would have to write `if dpkg -l | grep -q…` for every
  package check.
- (c) Salt/Chef/Puppet are heavier; agent-based; overkill for a CLI tool.
- (d) Computer-use is the right answer ONLY for Windows GUI installers
  with no silent install path. Slow and brittle for everything else.

---

## D2 — Docker as the portable runtime, not native install

**Considered:**
- Native install everywhere (pip + system Ansible)
- Docker container that ships everything pre-baked
- Standalone PyInstaller binary

**Chose:** Docker (with native install also documented)

**Why:**
- **Ansible's control node does not run on Windows.** Native install on
  Windows means WSL2, which is friction for non-developer users.
- **One image works on Linux, Mac, Windows.** Docker Desktop hides the
  platform difference.
- **Reproducible builds.** Pinned versions in `requirements.txt`; no "works
  on my machine."

**Tradeoff:** Docker Desktop is heavy on Windows (uses ~2GB RAM idle).
Acceptable for an internal ops tool; would not be acceptable for an
end-user product.

---

## D3 — Password auth as the default credential path (not SSH keys)

**Considered:**
- SSH key auth only (most secure)
- Password auth via env var (simplest UX)
- Per-host hybrid (key for some, password for others)

**Chose:** Password auth as default; SSH key supported as alternative.

**Why:**
- The whole pitch to non-tech users is "give credentials and go." SSH key
  setup requires a one-time manual step (copy pubkey to VPS), which
  defeats that pitch.
- Most VPS providers hand customers a root password during provisioning.
  That password is what the operator already has.
- The Dockerfile installs `sshpass` so password auth works out of the box.
- Threat model: the password lives only in `.env` on the operator's local
  machine, transmitted over an encrypted SSH session to the operator's
  own VPS. Acceptable for an internal MSP tool.

**When SSH key auth is preferred:**
- Production fleet provisioning where the same agent runs unattended
  against many hosts. Then key + ssh-agent is cleaner.
- Compliance-sensitive customers who require key-only auth.

The inventory template supports both via `ansible_password` vs
`ansible_ssh_private_key_file`.

---

## D4 — Credentials never leave the operator's machine; LLM never sees them

**Why this boundary matters:** The agent calls Claude with the user's
request, OS facts, and playbook YAML. Credentials are not in any of those.
Ansible — running locally inside the container — reads `inventory/hosts.yml`
and `.env` to make the SSH connection. The LLM sees only the **alias**
`my-linux-vps`, never the IP/user/password.

**Practical consequence:** Even if a teammate uses a hosted version of the
agent later (web/bot), they would still need their own `.env` and inventory
on whatever server runs the agent. The credentials never traverse Anthropic.

**This is by design.** Do not break it by including credentials in the
playbook YAML or by passing them as part of the user prompt.

---

## D5 — One Ansible task per package (system prompt rule)

**The bug that forced this:** When Claude generated a single task installing
multiple packages as a list, Ansible reported the entire task as `changed`
if any one package needed installing. Our parser then bucketed the whole
task as "newly installed" — even for packages that were already present.

**Test case:** prompt `"install htop, tree, ncdu, and fail2ban"` against a
host where `htop` was pre-installed and the rest weren't. The agent
reported all four as newly installed (wrong; `htop` was already present).

**Fix (commit `1648f02`):** system prompt now mandates one apt task per
package, with the task name `"Install <package>"`. Ansible then reports
each task individually, and our parser buckets accurately.

**After fix:** same test case correctly reports `htop` as "Already present"
and the other three as "Newly installed."

**Tradeoff:** larger playbooks (4 tasks instead of 1 for 4 packages). For
typical 3–10 package requests this is negligible. For a 100-package fleet
sweep it would be slower; revisit then with a `loop` + `register` pattern.

See [05-learnings.md § per-package idempotency](05-learnings.md) for the
full debugging story.

---

## D6 — `VPS_PORT` separate from `VPS_HOST`

**Why this is even a decision:** When the operator put `VPS_HOST=1.2.3.4:6689`,
SSH could not parse it — the `host:port` shorthand is invalid for the SSH
protocol's hostname field.

**Fix:** `inventory/hosts.yml` now has separate `ansible_host` and
`ansible_port`, each backed by its own env var. `VPS_PORT` defaults to 22
when unset (`default(22, true)` in the Jinja expression).

**Lesson:** custom SSH ports are common (security-by-obscurity); make the
inventory schema first-class for them rather than hoping users get the
syntax right.

---

## D7 — Live-mount source in `docker-compose.yml`

**Why:** During iteration, every code change required a `docker compose
build` (~30s) before testing. Mounting `./agent` and `./main.py` into the
container at `/app/agent` and `/app/main.py` lets Python pick up changes on
the next run with no rebuild.

**Caveat:** If `requirements.txt` changes, you DO need to rebuild — the
mount only covers Python source, not installed packages.

**Production note:** For deployed bot/web versions, keep the mount in
docker-compose for dev but remove it (or use a separate compose file) in
production so the running code is the immutable image content.

---

## D8 — Pre-create `/root/.claude.json` in the Dockerfile

**Symptom:** Every run printed three "Claude configuration file not found"
warnings before the actual output. Came from the bundled Claude Code CLI's
startup code looking for an OAuth config we don't use (we use API key).

**Fix (commit `5b416cc`):** `RUN echo '{}' > /root/.claude.json` in the
Dockerfile. CLI sees the file, stops complaining.

**Why not remove the Claude Code CLI entirely?** We keep it installed so
operators using subscription auth (`claude login`) can still use it. The
empty file fixes the API-key path without breaking the subscription path.
