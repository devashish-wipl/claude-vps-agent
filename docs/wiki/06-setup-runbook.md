# 06 — Setup & Runbook

Operational steps for getting the agent running and using it day-to-day.

---

## First-time setup

### Prerequisites

- **Docker Desktop** running (Windows/Mac) or **Docker Engine** (Linux)
- **Git** (to clone the repo)
- **An Anthropic API key** OR a Claude Pro/Max subscription

### Clone and configure

```bash
git clone https://github.com/devashish-wipl/claude-vps-agent.git
cd claude-vps-agent

cp .env.example .env
cp inventory/hosts.example.yml inventory/hosts.yml
```

### Edit `.env`

Minimum for password-auth Linux target:

```
ANTHROPIC_API_KEY=sk-ant-…
VPS_HOST=1.2.3.4
VPS_PORT=22
VPS_USER=root
VPS_PASSWORD=your-vps-root-password
```

If using Claude subscription instead of API key:
1. Install Claude Code CLI: `npm install -g @anthropic-ai/claude-code`
2. Run `claude login`
3. Leave `ANTHROPIC_API_KEY` blank in `.env`

### Edit `inventory/hosts.yml`

For one Linux VPS via password:

```yaml
all:
  hosts:
    my-linux-vps:
      ansible_host: "{{ lookup('env', 'VPS_HOST') }}"
      ansible_port: "{{ lookup('env', 'VPS_PORT') | default(22, true) }}"
      ansible_user: "{{ lookup('env', 'VPS_USER') }}"
      ansible_password: "{{ lookup('env', 'VPS_PASSWORD') }}"
      ansible_become_password: "{{ lookup('env', 'VPS_PASSWORD') }}"
      ansible_ssh_common_args: "-o StrictHostKeyChecking=no"
```

For multiple hosts, add more entries under `hosts:` with their own env-var
references (`VPS2_HOST`, `VPS2_PASSWORD`, etc.) or hard-code values.

### Build the image (one-time, ~2 min)

```bash
docker compose build
```

Subsequent code edits to `agent/` or `main.py` do NOT require rebuilds —
they are live-mounted (see [04-decisions.md § D7](04-decisions.md)). Only
rebuild when `Dockerfile` or `requirements.txt` changes.

---

## Daily use

```bash
docker compose run --rm agent <host_alias> "<natural-language request>"
```

Examples:

```bash
docker compose run --rm agent my-linux-vps "install nginx, certbot, ufw"
docker compose run --rm agent my-linux-vps "configure ufw to allow 22, 80, 443 and enable it"
docker compose run --rm agent my-linux-vps "install Node.js 20 LTS from NodeSource"
docker compose run --rm agent my-linux-vps "install Python 3.12 with pip and venv (dry-run)"
```

The `(dry-run)` keyword in the prompt triggers `--check` mode: Ansible
reports what *would* change without changing anything.

### Reading the output

```
Newly installed: <packages that were just installed>
Already present: <packages that were already in desired state>
Failed:          <packages that errored, with one-line reasons>
```

If `Already present` includes packages from your request, that's the
**idempotency check** working — re-running is safe.

### When something fails

1. **Read the `Failed: …` reasons.** Most common: package not in distro
   repos (typo, or needs upstream repo added).
2. **The agent will usually retry once** — adapting the playbook (rename
   package, add repo). If it still fails, you'll see the second failure.
3. **Check the actual playbook** at `playbooks/generated/play_<uuid>.yml`
   to see exactly what it tried.
4. **Test connectivity manually** if probe failed:
   ```bash
   docker compose run --rm agent <host> "(does not matter — this won't run if probe fails)"
   # or directly:
   docker compose run --rm --entrypoint bash agent
   ansible <host> -i inventory/hosts.yml -m ping
   ```

---

## Common errors and fixes

| Error | Cause | Fix |
|---|---|---|
| `PROBE FAILED — could not resolve hostname X:Y` | `VPS_HOST` includes `:port` | Move port to `VPS_PORT` |
| `SSH connection ... timed out during banner exchange` | Wrong port, host down, or firewall | `Test-NetConnection <host> -Port <port>` from operator machine |
| `Permission denied (publickey,password)` | Wrong password or username | Verify `.env` values; try manual `ssh` |
| `sudo: a password is required` | `ansible_become_password` missing | Add it (usually = `VPS_PASSWORD`) |
| `Claude configuration file not found` (warning, not error) | Bundled CLI startup noise | Cosmetic only; fixed by Dockerfile pre-creation |
| Image not found / `unknown service: agent` | Compose can't read `docker-compose.yml` | Run from inside the project folder |
| `.env` changes don't take effect | File saved as `.env.txt` (Notepad) | `dir .env*` to check; rename if needed |

---

## Adding a new VPS

1. Add a new host entry in `inventory/hosts.yml`:

   ```yaml
   customer-foo-vps:
     ansible_host: "{{ lookup('env', 'FOO_HOST') }}"
     ansible_port: "{{ lookup('env', 'FOO_PORT') | default(22, true) }}"
     ansible_user: "{{ lookup('env', 'FOO_USER') }}"
     ansible_password: "{{ lookup('env', 'FOO_PASSWORD') }}"
     ansible_become_password: "{{ lookup('env', 'FOO_PASSWORD') }}"
     ansible_ssh_common_args: "-o StrictHostKeyChecking=no"
   ```

2. Add the env vars to `.env`:

   ```
   FOO_HOST=…
   FOO_PORT=22
   FOO_USER=root
   FOO_PASSWORD=…
   ```

3. Run against the new alias:

   ```bash
   docker compose run --rm agent customer-foo-vps "install nginx"
   ```

---

## Adding a Windows target

Pre-req on the VPS (one-time, run as Administrator):

```powershell
winrm quickconfig -q
winrm set winrm/config/service/auth '@{Basic="true"}'
winrm set winrm/config/service '@{AllowUnencrypted="true"}'   # testing only
```

Then in `inventory/hosts.yml`:

```yaml
my-windows-vps:
  ansible_host: 5.6.7.8
  ansible_user: Administrator
  ansible_password: "{{ lookup('env', 'WIN_PASSWORD') }}"
  ansible_connection: winrm
  ansible_port: 5986
  ansible_winrm_transport: ntlm
  ansible_winrm_server_cert_validation: ignore
```

Or for Server 2019+ with OpenSSH:

```yaml
my-windows-vps:
  ansible_host: 5.6.7.8
  ansible_user: Administrator
  ansible_password: "{{ lookup('env', 'WIN_PASSWORD') }}"
  ansible_shell_type: powershell
```

---

## Audit / forensics

Every playbook the agent ran is at:

```
playbooks/generated/play_<uuid>.yml
```

To see what the agent did over the last week:

```bash
ls -lt playbooks/generated/ | head -20
```

These files are gitignored. If you want long-term audit, ship them to S3
or a log aggregator on a cron.

---

## Updating the agent

```bash
git pull
docker compose build    # only if Dockerfile or requirements.txt changed
```

Check `git log` to see what changed. The wiki is at `docs/wiki/` and is
updated alongside code changes — read recent commits there too.
