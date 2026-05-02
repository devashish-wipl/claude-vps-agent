# CLAUDE.md

Orientation for any Claude (or human) starting work in this repo.

## What this project is (10-second version)

`claude-vps-agent` — Claude Agent SDK + Ansible inside Docker. Takes
plain-English VPS provisioning requests (*"install nginx and certbot"*),
detects the target's OS, generates an Ansible playbook, runs it, and
reports per-task changed/ok/failed status. Internal tooling for WIPL
(cloud + hosting MSP).

Always start by reading `docs/wiki/README.md` — it's the index for the
full project context.

---

## Context-loading guide — read these BEFORE working on…

Match your task to a row; load the listed files into context first. Don't
skip this — most "obvious" changes here unwind a deliberate decision
documented in `04-decisions.md`.

| Task | Files to load (in order) |
|---|---|
| **First time in this repo, any work** | `docs/wiki/README.md` → `01-overview.md` → `02-architecture.md` |
| **Debugging a regression / weird behavior** | `docs/wiki/05-learnings.md` first (L1–L10 cover most quirks) → then the relevant code file |
| **Changing the system prompt** | `agent/core.py` (`SYSTEM_PROMPT`) + `04-decisions.md` D5 + `05-learnings.md` L1 |
| **Adding/modifying an agent tool** | `agent/core.py` (`@tool` definitions) + `agent/tools.py` + `02-architecture.md` § "Two tools the agent has" |
| **Changing playbook/output parsing** | `agent/parsing.py` + `03-data-flow.md` § "What happens on errors" |
| **Touching credential handling** | `04-decisions.md` D3 + D4 + `inventory/hosts.example.yml` + `.env.example` — DO NOT break the "credentials never leave the operator's machine" boundary |
| **Adding a new VPS / inventory schema change** | `06-setup-runbook.md` § "Adding a new VPS" + `inventory/hosts.example.yml` |
| **Docker / build changes** | `Dockerfile` + `docker-compose.yml` + `04-decisions.md` D2, D7, D8 |
| **Building a frontend (web/bot)** | `07-roadmap.md` § "Frontend layer" + `agent/core.py` `run_agent()` (the function any frontend will call) + `03-data-flow.md` to understand what to surface |
| **Onboarding a teammate** | Hand them `06-setup-runbook.md` |
| **Understanding "what does Claude vs Ansible vs Docker actually do"** | `02-architecture.md` + `03-data-flow.md` + `08-glossary.md` |
| **Cost/auth questions (API key vs subscription)** | `06-setup-runbook.md` § "First-time setup" + `08-glossary.md` § "Subscription auth vs API key auth" |
| **Anything Windows-specific** | `05-learnings.md` L4, L5, L9, L10 + `06-setup-runbook.md` |

---

## Doc-update protocol — UPDATE THE WIKI AFTER YOUR WORK

The wiki is only useful if it stays current. **Treat doc updates as part
of the change, not optional cleanup.** A PR that changes behavior without
updating docs is incomplete.

After every task, ask: did I change…

| If you changed… | …then update |
|---|---|
| The system prompt, tool signatures, or parsing logic | `02-architecture.md` |
| The data flow (new step, new actor, new data crossing a boundary) | `03-data-flow.md` |
| Any architectural choice (new dependency, new pattern) | Add a new `D<N>` entry to `04-decisions.md` — capture what you considered and why you chose what you chose |
| Hit a bug, quirk, or misconception worth remembering | Add a new `L<N>` entry to `05-learnings.md` — symptom, root cause, fix, verification |
| Setup steps, env vars, or compose file | `06-setup-runbook.md` (and `.env.example` / `inventory/hosts.example.yml` if those changed) |
| Roadmap items (started / shipped / dropped) | `07-roadmap.md` — move shipped items out, mark dropped items with why |
| Introduced or renamed a term | `08-glossary.md` |

**Rule of thumb:** if a future Claude session would be confused without
your update, you owe the update. The cost of writing it now is much lower
than the cost of someone re-debugging it next month.

### Doc-update commit conventions

- Bundle doc updates into the **same commit** as the code change they
  describe. Don't split them into a separate "docs:" commit unless the
  doc work is genuinely standalone (typo fix, reorganization).
- Reference commit hashes in the wiki when documenting fixes (see
  `05-learnings.md` L1 referencing commit `1648f02` for an example).
- Use today's date (UTC, ISO format `YYYY-MM-DD`) for any "Date:" stamps
  in `04-decisions.md` or `05-learnings.md`.

---

## Project working agreements

- **Don't commit `.env` or `inventory/hosts.yml`.** Both are gitignored.
  If you need to add a config option, update `.env.example` and
  `inventory/hosts.example.yml` instead.
- **Test against a real VPS before pushing** behavior changes. The agent's
  output format is the contract; regressions there break downstream
  consumers (and break operator trust fast).
- **Generated playbooks** (`playbooks/generated/`) are local audit logs,
  also gitignored. Never put fixtures or sample playbooks there — they'll
  be lost.
- **Branch / PR style:** for now, direct pushes to `main` are fine
  (single-developer cadence). When the team grows, switch to PRs.
- **Commit message style:** short imperative subject. Prefix with
  `fix:` / `feat:` / `docs:` / `polish:` / `chore:` for clarity.
  Example: `fix: enforce one-task-per-package so per-package idempotency
  report is accurate`.

---

## Quick file map

```
agent/core.py        — Claude Agent SDK setup, tool definitions, SYSTEM_PROMPT
agent/tools.py       — probe_host_impl, run_playbook_impl (subprocess to ansible)
agent/parsing.py     — Ansible JSON → CHANGED / OK / FAILED summary
main.py              — CLI entrypoint (loads .env, calls run_agent)
Dockerfile           — Python 3.12 + Ansible + sshpass + Node + Claude CLI
docker-compose.yml   — service def, env_file, volume mounts
inventory/           — hosts.example.yml (template), hosts.yml (gitignored, real)
playbooks/generated/ — every playbook the agent has run (gitignored audit log)
docs/wiki/           — full project context (READ THIS)
```

---

## When in doubt

1. Read `docs/wiki/README.md` and follow the routing above.
2. Look in `docs/wiki/05-learnings.md` for "we already hit this."
3. Ask in plain English; the agent is forgiving and most surprises are
   already documented.
