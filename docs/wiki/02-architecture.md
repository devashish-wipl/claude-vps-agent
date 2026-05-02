# 02 — Architecture

## Components and roles

```
┌──────────────────────────────────────────────────────────────┐
│  Operator's machine (any OS with Docker)                     │
│                                                              │
│  ┌──── Docker container (ephemeral, ~30s lifespan) ────┐    │
│  │                                                     │    │
│  │  Python entrypoint (main.py)                        │    │
│  │       │                                             │    │
│  │       ▼                                             │    │
│  │  agent/core.py                                      │    │
│  │   ├─ ClaudeAgentOptions (system prompt, tools)      │    │
│  │   ├─ create_sdk_mcp_server(name="vps", tools=[…])   │    │
│  │   └─ async for msg in query(prompt, options): …     │    │
│  │       │                                             │    │
│  │       ▼ when Claude calls a tool…                   │    │
│  │  agent/tools.py                                     │    │
│  │   ├─ probe_host_impl  → subprocess: `ansible -m setup`  │
│  │   └─ run_playbook_impl → subprocess: `ansible-playbook` │
│  │       │                                             │    │
│  │       ▼                                             │    │
│  │  agent/parsing.py                                   │    │
│  │       parses Ansible JSON callback output           │    │
│  │       into CHANGED / OK / FAILED / SKIPPED buckets  │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
              │                                    │
              │ HTTPS to api.anthropic.com          │ SSH/WinRM to target VPS
              ▼                                    ▼
       Claude API (the brain)              Customer VPS (any distro)
```

## Component responsibilities

| Component | Responsibility | Why it lives here |
|---|---|---|
| **Claude Agent SDK** | Drives the conversation loop, manages tool calls, streams messages | Built for exactly this — agents that use tools |
| **Custom MCP server (in-process)** | Wraps `probe_host` and `run_playbook` as callable tools for the agent | SDK's `create_sdk_mcp_server` is the canonical way to expose Python functions as tools |
| **Ansible (control node)** | Generates SSH/WinRM connections, runs modules idempotently, reports per-task status | 20 years of cross-platform module coverage — we're not rebuilding it |
| **Ansible (managed nodes)** | The customer VPS itself runs whatever the playbook says | This is where actual installs happen |
| **Docker** | Ships Python + Ansible + sshpass + Node + Claude CLI as one portable image | Ansible doesn't run natively on Windows; Docker hides that |
| **`docker-compose.yml`** | Mounts inventory, generated playbooks, SSH keys, and Claude auth into the container | Live mounts let edits take effect without rebuilds |

## Two tools the agent has

Defined in `agent/core.py` via the `@tool` decorator:

### `probe_host(host)`

Runs `ansible <host> -m setup` to gather OS facts (distribution, version,
package manager, architecture). Returns a JSON snippet the LLM uses to
decide which Ansible modules to use (`apt` vs `dnf` vs `win_chocolatey`).
**Always called first.** If it fails, the agent stops — does not run a
playbook blind.

### `run_playbook(playbook_yaml, host, check_mode=False)`

1. Saves the YAML string to `playbooks/generated/play_<uuid>.yml` (audit log).
2. Spawns `ansible-playbook` as a subprocess with
   `ANSIBLE_STDOUT_CALLBACK=json` so output is parseable.
3. Pipes stdout into `parsing.summarize_run()` which returns a structured
   summary the LLM reads.

The `check_mode=True` flag passes `--check` to Ansible (dry run, no actual
changes). Triggered when the user includes "(dry-run)" in their request.

## System prompt design

Lives in `agent/core.py` as `SYSTEM_PROMPT`. Key clauses:

- **Workflow gating:** `probe_host` MUST be called before any `run_playbook`.
- **Per-package tasks:** Each package becomes its own Ansible task. Without
  this, idempotency reporting is wrong (see
  [05-learnings.md § per-package idempotency](05-learnings.md)).
- **Output shape:** The LLM must answer in `Newly installed / Already present
  / Failed` format, no other prose. Predictable for downstream consumers.
- **Adapt-and-retry once:** On task failure, the LLM is allowed one
  adaptation attempt (rename package, add repo, switch module) before giving
  up. Prevents infinite loops.
- **Safety gate:** Destructive ops (`rm -rf`, `dd`, `mkfs`, dropping
  databases) require explicit user confirmation in the LLM's reply before
  running.

## What lives outside the container

| Thing | Where | Why |
|---|---|---|
| `.env` | Operator's host disk | Loaded via `env_file:` in compose; secrets stay local |
| `inventory/hosts.yml` | Operator's host disk, mounted | Same — credentials never baked into image |
| `~/.ssh/` | Mounted read-only | SSH keys stay on host |
| `~/.claude/` | Mounted | Claude Code OAuth (subscription auth path) |
| `playbooks/generated/` | Mounted read-write | Audit log persists across runs |

## What we deliberately did NOT build

- **No persistent agent process.** Each invocation spins up a container,
  does the work, exits. Stateless. Avoids stale processes / drift / a whole
  class of bugs.
- **No DB.** Inventory is YAML on disk; audit log is files in
  `playbooks/generated/`. Sufficient for current scale.
- **No web frontend (yet).** See [07-roadmap.md](07-roadmap.md).
- **No multi-host fan-out.** Could be added later (`ansible-playbook` already
  supports it via `-l "host1,host2"`); current CLI is single-host.
