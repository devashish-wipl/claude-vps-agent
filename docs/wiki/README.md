# claude-vps-agent — Project Wiki

Persistent context for the agent: what it is, how it works, why it's built
this way, what bugs we've found, and what's next. Optimized for an LLM (or
new contributor) to ingest and bring themselves up to speed.

**Project:** AI agent that provisions VPS hosts on natural-language requests.
**Owner:** WIPL (cloud + hosting MSP, Jaipur).
**Started:** 2026-05-02.
**Current state:** working CLI MVP. Web/bot frontends are open design questions.

## Index

1. [Overview — what it is, who it's for](01-overview.md)
2. [Architecture — components and their roles](02-architecture.md)
3. [Data flow — full request lifecycle, who sees what](03-data-flow.md)
4. [Decisions — why we chose what we chose](04-decisions.md)
5. [Learnings — bugs, gotchas, misconceptions corrected](05-learnings.md)
6. [Setup & runbook — operational steps](06-setup-runbook.md)
7. [Roadmap — frontend options, future work](07-roadmap.md)
8. [Glossary — key terms](08-glossary.md)

## How to use this wiki

- **New LLM session:** start at `01-overview.md`, then `02-architecture.md`,
  then `03-data-flow.md`. That gets you 80% of the context.
- **Debugging a regression:** check `05-learnings.md` first — most weird
  behaviors we've seen are documented there with fixes.
- **Adding a feature:** read `04-decisions.md` to understand the constraints
  the project chose to live within. Then `07-roadmap.md` for what's planned.
- **Onboarding a teammate:** start with `06-setup-runbook.md`.

## Repository layout (mirror of project root)

```
claude-vps-agent/
├── main.py                    CLI entrypoint
├── agent/
│   ├── core.py                Claude Agent SDK orchestration + system prompt
│   ├── tools.py               probe_host, run_playbook (subprocess → ansible)
│   └── parsing.py             ansible JSON → CHANGED/OK/FAILED summary
├── inventory/hosts.example.yml
├── playbooks/generated/       every playbook the agent runs (audit log)
├── Dockerfile + docker-compose.yml
├── requirements.txt + .env.example
└── docs/wiki/                 this folder
```
