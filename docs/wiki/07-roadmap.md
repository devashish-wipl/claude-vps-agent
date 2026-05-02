# 07 — Roadmap

Open questions and future work, ranked by likely value to WIPL.

---

## Frontend layer (next major decision)

Currently CLI-only. Three frontend options under consideration; **management
will pick** based on team workflow:

### Option A — Local web dashboard (Streamlit / Gradio)

- ~30 lines on top of existing `run_agent()`.
- Browser UI: dropdown of hosts + text box + Run button + result panel.
- Runs as a second service in `docker-compose.yml`.
- **Best for:** desk-bound engineers, internal tool use.
- **Effort:** ~1 hour to MVP.

### Option B — Chat bot (WhatsApp / Slack / Telegram)

- Webhook server (Flask/FastAPI) running 24/7 on a dedicated VPS.
- Receives messages from the chat platform, calls `run_agent()`,
  replies in-thread.
- **WhatsApp via Meta Cloud API** is the strongest fit for India-based
  WIPL — most teams already coordinate there. Free for first 1k
  conversations/month.
- Alternatives: Twilio WhatsApp (paid, faster setup), Slack (best for
  internal teams already on Slack), Telegram (easy bot API).
- **Best for:** mobile / on-call / "customer is on the line, install X now"
  workflows.
- **Effort:** ~1 day end-to-end (Meta verification is the slow part).

### Option C — Full internal product (multi-user web app)

- Login (Google Workspace SSO), VPS registry UI, request history, RBAC,
  approval workflow for risky ops, cost dashboard.
- "WIPL Internal Provisioning Console."
- **Best for:** scaling beyond ~5 operators.
- **Effort:** ~2 weeks.

### Recommendation

Build **A first** for instant feedback; then watch how it gets used to
decide between **B** and **C**. The agent code (`agent/`) stays unchanged
across all three — frontends are thin layers calling `run_agent()`.

---

## Agent capability extensions

### Multi-host fan-out
Currently single-host per invocation. Ansible already supports
`-l "host1,host2,host3"`. Add a `--hosts host1,host2` CLI flag and pass
through. Useful for fleet patches, security rollouts.

### Pre-flight cloud-init layer
For *truly* first-boot bootstrapping (before SSH is even up), generate a
cloud-init YAML the operator can paste into their VPS provider's UI. The
cloud-init does the bare minimum (set hostname, install Python, allow SSH
key) so the agent can take over from there.

### Safer defaults for destructive ops
Currently the system prompt asks for confirmation in the LLM's reply. A
better pattern: a dedicated `confirm_destructive(reason)` tool that pauses
the agent and surfaces the prompt to the user (CLI or UI), waits for
explicit yes/no, then continues.

### Vault-encrypted secrets
For multi-operator setups, replace plaintext `.env` with `ansible-vault`-
encrypted secrets. Operator unlocks at runtime with a vault password.

### Per-customer inventory split
Inventory grows large with many customers. Split into
`inventory/customers/<customer-id>.yml` files; agent loads the right one
based on the host alias namespace.

---

## Observability

### Cost tracking
Add per-invocation logging of Anthropic API token usage (the SDK exposes
this in the result). Surface monthly spend per operator / per customer.

### Run telemetry
Currently no metrics. Add a minimal Prometheus exporter:
- `agent_runs_total{outcome="success|failed",host=…}`
- `agent_packages_changed_total`
- `agent_run_duration_seconds`

### Centralized audit log
`playbooks/generated/` files are local. For compliance, ship them to S3
on cron or stream to a log aggregator (Loki, ELK).

---

## Open questions

- **Should the agent remember anything across runs?** Current model is
  stateless — each invocation is a fresh conversation. Pros: simpler, no
  cache invalidation. Cons: re-probes the OS every time. Could cache OS
  facts per host with a short TTL. Probably not worth it until cost or
  latency forces it.
- **How do we handle long-running tasks (e.g., compiling something)?**
  Ansible blocks until the task completes; for a chat bot this could
  exceed message timeouts. May need async dispatch + status polling.
- **What about non-package operations** (uploading files, editing configs,
  managing users)? Ansible covers all of these via different modules; the
  system prompt would need updating to acknowledge non-`apt`/`dnf` requests
  cleanly. Currently focused on package installs because that's the most
  common request type.
- **Multi-tenant safety:** if WIPL eventually exposes this beyond ops, we
  need strict isolation between customers' inventories. Not a concern for
  internal-only use today.
