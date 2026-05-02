# claude-vps-agent

A portable AI agent that provisions VPS hosts on natural-language requests.
Powered by the **Claude Agent SDK** (the brain) + **Ansible** (the hands).

Works against:
- Linux VPS (Ubuntu, Debian, RHEL, Fedora, Alpine, Arch, ...) over SSH
- Windows VPS (Server 2019+, Win10/11) over WinRM or OpenSSH

Handles idempotency natively via Ansible: re-running the same request never
double-installs. The agent reports clearly which packages were *newly
installed*, which were *already present*, and which *failed and why*.

---

## Quick demo (after setup)

Assumes you've completed the [Setup](#setup) section once — repo cloned,
Docker Desktop running, `.env` and `inventory/hosts.yml` filled in, and
`docker compose build` already executed.

### Step 1 — Open a terminal in the project folder

**Windows (PowerShell):**
```powershell
cd "C:\Users\<you>\Desktop\claude-vps-agent"
```

**Linux / macOS:**
```bash
cd ~/Desktop/claude-vps-agent
```

### Step 2 — Pull latest (if you've pushed commits from elsewhere)

```bash
git pull
```

### Step 3 — Run the agent

```bash
docker compose run --rm agent my-linux-vps "install htop, tree, ncdu, cowsay, and figlet"
```

Expected output (baseline VPS where only `htop` is pre-installed):

```
Newly installed: tree, ncdu, cowsay, figlet
Already present: htop
Failed:          none
```

### Step 4 — Re-run the exact same command (the idempotency punchline)

```bash
docker compose run --rm agent my-linux-vps "install htop, tree, ncdu, cowsay, and figlet"
```

Now the output shifts:

```
Newly installed: none
Already present: htop, tree, ncdu, cowsay, figlet
Failed:          none
```

Same command, different report — because the agent knows everything is
already in the desired state. **This is the killer feature for safe fleet
ops:** you can re-run blindly across hundreds of VPSes without breaking
anything.

### What you've just demonstrated

- **Step 3 → Newly installed bucket** — the agent installed 4 fresh packages
- **Step 3 → Already present bucket** — proved per-package idempotency
- **Step 4** — proved full-run idempotency: zero changes on a redundant request
- **Failed bucket** — empty in both runs, but if it weren't, you'd see the
  per-package reason and the agent would attempt a single adapt-and-retry

---

## How it works

```
  user request (natural language)
            │
            ▼
   ┌──────────────────────┐       ┌────────────────────┐
   │ Claude Agent SDK     │──────▶│ Tool: probe_host   │  detects OS family
   │ (loop, plans, retries)│       └────────────────────┘
   │                      │       ┌────────────────────┐
   │                      │──────▶│ Tool: run_playbook │  generates + runs YAML
   └──────────────────────┘       └────────────────────┘
            │                                │
            ▼                                ▼
        report back                   Ansible → SSH/WinRM → VPS
```

Claude generates an Ansible playbook tailored to the detected OS, runs it,
parses the structured result, and adapts on failure (e.g. retries with a
different package name on a different distro).

---

## Setup

You need **one of**:
- A **Claude Pro or Max subscription** (free of per-token cost), via the
  Claude Code CLI, OR
- An **Anthropic API key** from <https://console.anthropic.com> (pay-per-use)

Pick the install path that suits your machine.

### Option A — Docker (most portable, recommended for sharing)

Works the same on Linux, macOS, and Windows (with Docker Desktop).

```bash
git clone <your-repo-url> claude-vps-agent
cd claude-vps-agent
cp .env.example .env       # add ANTHROPIC_API_KEY if using API auth
cp inventory/hosts.example.yml inventory/hosts.yml
# edit inventory/hosts.yml with your VPS details

docker compose build
docker compose run --rm agent my-linux-vps "install nginx, certbot, ufw and open ports 80/443"
```

If you're on a **Claude subscription** instead of API key, run `claude login`
on your host once; `docker-compose.yml` mounts `~/.claude` into the container
so the OAuth token is reused.

### Option B — Native install (Linux / macOS)

```bash
git clone <your-repo-url> claude-vps-agent
cd claude-vps-agent

# 1. Install Claude Code (handles auth with your subscription) — optional if using API key
npm install -g @anthropic-ai/claude-code
claude login        # only if using Pro/Max subscription

# 2. Python deps
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Ansible (control node — Linux/macOS only)
pip install ansible pywinrm   # pywinrm only needed for Windows targets

# 4. Configure
cp .env.example .env
cp inventory/hosts.example.yml inventory/hosts.yml
# edit inventory/hosts.yml

# 5. Run
python main.py my-linux-vps "install docker, docker-compose, and nodejs 20"
```

### Option C — Windows (native, without Docker)

Ansible's control node does not run on Windows directly. Use **WSL2**:

```powershell
wsl --install -d Ubuntu-22.04        # one-time
wsl                                  # drop into Ubuntu shell
# then follow Option B inside WSL
```

Your Windows-side SSH keys at `C:\Users\<you>\.ssh\` are visible from WSL at
`/mnt/c/Users/<you>/.ssh/` — point your inventory there or copy them into
`~/.ssh/` inside WSL.

---

## Inventory: defining your hosts

Edit `inventory/hosts.yml`. Two example hosts (Linux + Windows):

```yaml
all:
  hosts:
    my-linux-vps:
      ansible_host: 1.2.3.4
      ansible_user: root
      ansible_ssh_private_key_file: ~/.ssh/id_rsa

    my-windows-vps:
      ansible_host: 5.6.7.8
      ansible_user: Administrator
      ansible_password: "{{ lookup('env', 'WIN_PASSWORD') }}"
      ansible_connection: winrm
      ansible_winrm_server_cert_validation: ignore
      ansible_port: 5986
      ansible_winrm_transport: ntlm
```

For Windows targets:
- Either enable **WinRM** (`winrm quickconfig` on the VPS), or
- Install **OpenSSH Server** (Server 2019+) and use the same `ansible_user` /
  `ansible_ssh_private_key_file` pattern as Linux.

---

## Usage examples

```bash
# Linux: bootstrap LAMP stack
python main.py my-linux-vps "install Apache, MySQL 8, PHP 8.2 with common modules, enable services on boot"

# Linux: container host
python main.py my-linux-vps "install Docker CE, docker-compose plugin, add user 'devashish' to docker group"

# Windows: dev tools
python main.py my-windows-vps "install Git, Node.js 20 LTS, and VSCode via Chocolatey"

# Re-run safely (idempotent)
python main.py my-linux-vps "install nginx and ufw"
# → reports "ALREADY IN DESIRED STATE: nginx, ufw"
```

Output format the agent will return:

```
CHANGED (2):
  - Install nginx on my-linux-vps
  - Enable nginx service on my-linux-vps

ALREADY IN DESIRED STATE / OK (1):
  - Install ufw on my-linux-vps  (no change needed)

FAILED (1):
  - Install postgresql-15 on my-linux-vps
      reason: No package matching 'postgresql-15' is available (distro repo only has 14)
```

When something fails, the agent will usually try once more with an adapted
playbook (e.g. swap to `postgresql-14`, or add the upstream PGDG repo first)
before giving up.

---

## Safety

- The agent never runs `rm -rf`, `dd`, `mkfs`, `fdisk`, or partition ops
  without flagging them in its plan first.
- All generated playbooks are saved under `playbooks/generated/` with a
  unique ID — full audit trail.
- Dry-run any request by appending `(dry-run)` to your prompt; the agent
  will pass `--check` to Ansible.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `PROBE FAILED` | Host unreachable / wrong key | `ansible <host> -i inventory/hosts.yml -m ping` |
| `Permission denied (publickey)` | SSH key not loaded | `ssh-add ~/.ssh/id_rsa` or set `ansible_ssh_private_key_file` |
| `sudo: a password is required` | No NOPASSWD sudo | add `--ask-become-pass`, or fix sudoers on VPS |
| Windows `winrm` errors | WinRM not enabled | run `winrm quickconfig` on the VPS as admin |
| Claude SDK auth error | Not logged in & no API key | `claude login` OR set `ANTHROPIC_API_KEY` in `.env` |

---

## Project layout

```
claude-vps-agent/
├── main.py                  # CLI entrypoint
├── agent/
│   ├── core.py              # Claude Agent SDK orchestration + system prompt
│   ├── tools.py             # probe_host, run_playbook (the agent's hands)
│   └── parsing.py           # Ansible JSON output → human-readable summary
├── inventory/
│   └── hosts.example.yml    # template for your hosts
├── playbooks/generated/     # every playbook the agent runs lands here (audit)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```
