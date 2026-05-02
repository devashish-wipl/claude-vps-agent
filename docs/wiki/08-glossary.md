# 08 — Glossary

Key terms used across the project. New contributors should read this first.

---

**Agent**
In this codebase: the Claude-powered orchestrator (`agent/core.py`) that
takes a natural-language request and drives Ansible to fulfill it. In the
broader Anthropic sense: an LLM in a tool-use loop with a goal.

**Ansible**
The open-source automation tool that does the actual work on target hosts.
Reads YAML "playbooks" and executes them over SSH (Linux) or WinRM
(Windows). 20+ years of cross-platform module coverage.

**Audit log**
The collection of `playbooks/generated/play_<uuid>.yml` files — every
playbook the agent has run, kept on disk for forensics and reproducibility.

**Become / `become: true`**
Ansible's privilege-escalation directive. On Linux, equivalent to `sudo`.
Required for system-package installs, service management, etc.

**Brain vs hands**
Mental model for this project: **Claude is the brain** (understands
requests, generates playbooks, adapts to errors); **Ansible is the hands**
(executes reliably and idempotently).

**Changed / OK / Failed / Skipped**
Ansible's per-task result statuses. **Changed** = work was done. **OK** =
already in desired state, no work needed (this is what makes idempotency
visible). **Failed** = errored. **Skipped** = conditionally not run.

**Claude Agent SDK**
Anthropic's Python/TS library for building agents that use tools. Provides
the `query()` loop, `@tool` decorator, and MCP server helper. Lives in
`agent/core.py`.

**Claude Code CLI**
The command-line app `claude` from `@anthropic-ai/claude-code`. Bundled
in the Dockerfile because the Agent SDK uses it for OAuth-based
subscription auth. Operators using API key auth ignore it.

**Container**
A running instance of a Docker image. Ephemeral in our setup (runs once,
exits, gets `--rm`'d).

**Control node** (Ansible term)
The machine running `ansible-playbook` — i.e., the Docker container in
our setup. Does NOT have to be the operator's machine; it's wherever the
container runs.

**Docker / Docker Desktop**
The container runtime. **Docker Engine** on Linux, **Docker Desktop** on
Windows/Mac (which uses a hidden Linux VM).

**Dry-run / check mode**
Ansible's `--check` flag: simulates what would change without actually
changing anything. Triggered in our agent by including "(dry-run)" in
the user's prompt.

**Idempotency**
A property of an operation: running it once or running it many times has
the same end state. `apt install nginx` is idempotent (already-installed
nginx is a no-op). `echo line >> file` is NOT (each run appends another
line). Ansible modules are designed to be idempotent.

**Image** (Docker)
The recipe — the built `claude-vps-agent:latest` artifact. Containers are
created from images.

**Inventory**
The Ansible YAML file (`inventory/hosts.yml`) that maps host aliases to
real connection details (IP, port, user, password, key). Aliases are what
the LLM sees; real values are what Ansible uses.

**Live-mount**
Mounting a host directory into the container so changes on the host are
visible inside the container without rebuilding the image. We do this for
`agent/`, `main.py`, `inventory/`, `playbooks/generated/`, `~/.ssh/`,
`~/.claude/`.

**Managed node** (Ansible term)
The target host being configured — i.e., the customer VPS.

**MCP server / `create_sdk_mcp_server`**
"Model Context Protocol" — Anthropic's open protocol for exposing tools
to LLMs. The SDK has a helper to create an in-process MCP server from
Python functions. We use it to expose `probe_host` and `run_playbook`.

**Operator**
The human running the agent. Today an internal WIPL engineer; future:
non-tech teammates via web/bot frontends.

**Playbook** (Ansible term)
A YAML file describing a sequence of tasks to run against hosts. The
agent generates one playbook per request, saves it to
`playbooks/generated/`, then runs it.

**Probe** / `probe_host`
First tool the agent calls. Runs `ansible <host> -m setup` to learn the
target's OS facts. Required before generating any playbook so the agent
picks the right modules (`apt` vs `dnf` vs `win_chocolatey`).

**SSH key vs password auth**
Two ways to authenticate to a Linux VPS. Key auth is more secure but
requires copying a pubkey to the VPS first. Password auth is simpler for
"give credentials and go" — supported in our default inventory via
`ansible_password` + `sshpass`.

**Subscription auth vs API key auth**
Two ways to authenticate the agent to Claude. **Subscription** = use a
Pro/Max plan via `claude login` (free of per-token cost, capped at plan
limits). **API key** = `ANTHROPIC_API_KEY` from console.anthropic.com
(pay per token). Either works.

**System prompt**
The instructions given to Claude that bound its behavior. Lives at the
top of `agent/core.py` as `SYSTEM_PROMPT`. Defines the workflow, output
format, error-handling rules, and safety gates.

**Task** (Ansible term)
A single unit of work in a playbook, like "Install nginx" or "Enable
service nginx." Each task uses one Ansible module.

**Tool / tool call**
In LLM parlance: a function the agent can call to take an action or
fetch information. We expose two: `probe_host` and `run_playbook`.

**WinRM**
Windows Remote Management. The protocol Ansible uses to connect to
Windows targets that don't have OpenSSH. Replaced by OpenSSH on
Server 2019+.

**WSL / WSL2**
Windows Subsystem for Linux. Lets Linux-native tools run on Windows.
Our project does NOT require WSL because Docker Desktop runs the Linux
container itself; WSL is only needed if you want to run Ansible
natively on Windows without Docker.
