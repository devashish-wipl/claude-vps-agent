# 03 — Data Flow

End-to-end walkthrough of one invocation, with explicit notes on which
party sees which data.

## The trigger

The operator runs:

```bash
docker compose run --rm agent my-linux-vps "install nginx and certbot"
```

`my-linux-vps` is the **inventory alias** — it maps to a real IP/user/password
combination via `inventory/hosts.yml` + `.env`. The alias is what the LLM
sees; the real IP is never sent to the LLM.

## Step-by-step lifecycle

```
①  Operator types command
       │
       ▼
②  Docker Desktop spins up a container from claude-vps-agent:latest
       │  (mounts: .env, inventory/, playbooks/generated/, ~/.ssh/, ~/.claude/)
       ▼
③  python main.py my-linux-vps "install nginx and certbot"
       │  loads .env → ANTHROPIC_API_KEY, VPS_HOST, VPS_PORT, VPS_USER, VPS_PASSWORD
       ▼
④  agent/core.py: run_agent() starts an async query loop
       │  prompt sent to Claude:
       │     SYSTEM: <SYSTEM_PROMPT>
       │     USER:   "Target host (inventory alias): my-linux-vps
       │              Request:
       │              install nginx and certbot"
       ▼
⑤  Claude → tool call: probe_host(host="my-linux-vps")
       │
       ▼
⑥  agent/tools.py: probe_host_impl shells out:
       │     ansible my-linux-vps -i inventory/hosts.yml -m setup -a filter=…
       │  Ansible reads inventory/hosts.yml + env vars → SSH connection →
       │  runs `setup` module on VPS → returns OS facts JSON.
       ▼
⑦  Tool returns to Claude:
       │     { "system": "Linux", "os_family": "Debian",
       │       "distribution": "Ubuntu", "version": "24.04",
       │       "pkg_mgr": "apt", "architecture": "x86_64" }
       ▼
⑧  Claude generates an Ansible playbook YAML. (One task per package per the
       │  system prompt rule.)
       ▼
⑨  Claude → tool call: run_playbook(playbook_yaml=<…>, host="my-linux-vps")
       │
       ▼
⑩  agent/tools.py: run_playbook_impl
       │   • saves YAML → playbooks/generated/play_a3f2b9e1.yml
       │   • spawns: ansible-playbook play_a3f2b9e1.yml -i inventory/hosts.yml
       │              -l my-linux-vps  (with ANSIBLE_STDOUT_CALLBACK=json)
       │   • Ansible opens fresh SSH session to VPS, runs each task.
       ▼
⑪  Ansible returns JSON to stdout. agent/parsing.py: summarize_run() buckets
       │  every (task, host) pair into:
       │     CHANGED       — task did work; package was newly installed
       │     OK            — task ran but nothing needed changing (idempotent)
       │     SKIPPED       — task was conditionally skipped
       │     FAILED        — task errored; reason captured
       │     UNREACHABLE   — host couldn't be contacted
       ▼
⑫  Tool returns the summary text to Claude.
       ▼
⑬  Claude formats the user-facing reply per the system prompt's exact format:
       │     Newly installed: nginx, certbot
       │     Already present: ufw
       │     Failed:          none
       ▼
⑭  agent/core.py prints the reply. Container exits. Docker auto-removes it
       (--rm). Next invocation starts fresh.
```

## Who sees what (data ownership)

| Actor | Sees | Does NOT see |
|---|---|---|
| **Operator** | Their request, the agent's structured reply, the audit playbook in `playbooks/generated/` | Internal Ansible JSON (parsed away) |
| **Claude / Anthropic** | The user's request text, OS facts, the playbook YAML it generated, task statuses | VPS credentials, real IP (only the alias), .env contents, SSH keys |
| **Ansible (in container)** | Inventory file, `.env`, generated playbook, SSH session output | The conversation with Claude |
| **Customer VPS** | The SSH session and the commands Ansible runs | Anything else about the orchestration |
| **Docker Desktop** | Acts as a transport layer; sees no application data | — |
| **WhatsApp/Slack (future)** | Only the chat messages, not the YAML or credentials | — |

This separation is not accidental — it's why credentials can stay local
even when the agent runs on a remote server. See
[04-decisions.md § credential boundary](04-decisions.md).

## Two simultaneous network conversations

For each invocation, the container has two outbound connections open:

1. **Container → `api.anthropic.com`** over HTTPS (Claude reasoning)
2. **Container → customer VPS** over SSH (or WinRM for Windows targets)

These are independent. The operator's machine forwards both via its
internet connection; nothing weird is happening at the network layer.

## What happens on errors

| Error | Where caught | What the user sees |
|---|---|---|
| Inventory alias not found | `probe_host_impl` | "PROBE FAILED for host=…" with the `ansible … -m ping` debug command to run |
| SSH refused / key wrong | `probe_host_impl` (Ansible's setup fails) | Same — full stderr in the report |
| Wrong package name | `run_playbook_impl` reports task as FAILED | Claude sees the error, adapts the playbook (rename / add repo), retries ONCE |
| Ansible itself crashes (syntax error in playbook) | `parsing._raw_failure_report` falls back to raw stdout/stderr | "Playbook execution returned non-JSON output" + raw output — Claude can still reason about it |
| Claude hits `max_turns` (12) | SDK exits the loop | Last partial reply printed; user re-runs |
| Container can't reach Claude API | Network error from SDK | Stack trace printed; check `ANTHROPIC_API_KEY` and connectivity |

## Audit trail

Every playbook the agent runs is preserved at
`playbooks/generated/play_<uuid>.yml`. To see what the agent did historically:

```bash
ls -lt playbooks/generated/   # newest first
cat playbooks/generated/play_a3f2b9e1.yml
```

These are gitignored (they accumulate fast and contain target-specific
detail). For long-term audit, ship them to a log aggregator or S3.
