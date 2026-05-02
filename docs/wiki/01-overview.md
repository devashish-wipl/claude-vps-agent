# 01 — Overview

## What it is

`claude-vps-agent` is an AI agent that takes plain-English requests like
*"install Python 3.12, nginx, and certbot"* and executes them on a target VPS.
It works against both Linux (over SSH) and Windows (over WinRM or OpenSSH)
hosts.

It is portable: the entire toolchain runs inside a Docker container so the
same project works identically on a Linux VPS, a Mac, or a Windows machine
with Docker Desktop. No WSL required.

## Who it's for

WIPL is a cloud + managed-hosting MSP. The agent's intended users are two
audiences:

1. **Internal engineers** who provision and maintain customer VPSes. The CLI
   gives them speed and consistency.
2. **Non-technical teammates** (sales, support, ops) who shouldn't have to
   know Ansible YAML or distro package names. A future web/bot frontend (see
   [07-roadmap.md](07-roadmap.md)) will surface the agent to them.

## Why an AI agent (vs a static script)?

Three things a static provisioning script cannot do well:

1. **Speak natural language.** A teammate can say "install the LAMP stack and
   harden the firewall" without learning Ansible syntax or memorizing exact
   package names per distro.
2. **Adapt to the OS.** Same request → different YAML on Ubuntu vs CentOS vs
   Windows. The agent probes the host first and picks the right modules
   (`apt`, `dnf`, `pacman`, `win_chocolatey`, …).
3. **Recover from errors.** When `postgresql-15` isn't in the distro repo,
   the agent reads the error, swaps to `postgresql-14`, or adds the upstream
   PGDG repo as a prior task, and retries. A static script would just die.

## What it is NOT

- **Not a customer-facing product.** This is internal tooling for WIPL ops.
- **Not a configuration-management replacement.** It's a thin agent layer on
  top of Ansible. For complex stacks, use Ansible / Terraform directly.
- **Not a credential broker.** Credentials live in a local `.env` file on the
  operator's machine; they never reach Claude/Anthropic.
- **Not a real-time monitor.** The agent does discrete tasks ("install X")
  and exits. For continuous monitoring, use Prometheus / Grafana / etc.

## Constraints we live within

- **Single host per invocation** (current MVP). The architecture supports
  fleet runs but the CLI passes one host at a time. Easy extension later.
- **Idempotency relies on Ansible.** We do not write our own state tracking.
  If a task isn't idempotent at the Ansible-module level, our reporting
  loses fidelity (see [05-learnings.md § per-package idempotency](05-learnings.md)).
- **Ansible's control node must be Unix-like.** Docker hides this on
  Windows; we never expose it as a user concern.
