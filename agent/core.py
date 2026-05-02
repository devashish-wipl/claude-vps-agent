"""Claude Agent SDK orchestration: defines the agent's tools, system prompt, and entry point."""
from __future__ import annotations

import asyncio
from pathlib import Path

from claude_agent_sdk import (
    ClaudeAgentOptions,
    create_sdk_mcp_server,
    query,
    tool,
)

from .tools import probe_host_impl, run_playbook_impl

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INVENTORY = PROJECT_ROOT / "inventory" / "hosts.yml"
PLAYBOOK_DIR = PROJECT_ROOT / "playbooks" / "generated"
PLAYBOOK_DIR.mkdir(parents=True, exist_ok=True)


@tool(
    "probe_host",
    "Detect OS family, distribution, version, and package manager of the target VPS. "
    "ALWAYS call this FIRST before generating any playbook so you pick the right modules.",
    {"host": str},
)
async def probe_host(args):
    text = await probe_host_impl(args["host"], INVENTORY)
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "run_playbook",
    "Execute an Ansible playbook (YAML string) against the target host. Returns a structured "
    "report listing tasks that CHANGED (newly applied), tasks that were ALREADY in desired state "
    "(idempotent no-ops), tasks that were SKIPPED, and tasks that FAILED with reasons.",
    {"playbook_yaml": str, "host": str, "check_mode": bool},
)
async def run_playbook(args):
    text = await run_playbook_impl(
        yaml_content=args["playbook_yaml"],
        host=args["host"],
        inventory=INVENTORY,
        playbook_dir=PLAYBOOK_DIR,
        check_mode=bool(args.get("check_mode", False)),
    )
    return {"content": [{"type": "text", "text": text}]}


SYSTEM_PROMPT = """You are a VPS provisioning agent for a cloud-hosting MSP.

Your job: take a plain-English request like "install nginx, certbot, fail2ban"
and execute it on the user's VPS via Ansible. You MUST use only the two tools
available: probe_host and run_playbook.

WORKFLOW (follow strictly):
1. Call probe_host(host) FIRST. Read the OS family, distribution, and pkg_mgr.
2. Generate a single Ansible playbook tailored to that OS:
   - Debian/Ubuntu  -> apt module (use update_cache: yes on first task)
   - RHEL/Fedora    -> dnf module
   - Alpine         -> apk module
   - Arch           -> pacman module
   - Windows        -> win_chocolatey / win_package / win_feature modules
3. Always set `become: true` on Linux when installing system packages.
4. For Windows, no `become` — Chocolatey runs as the connecting user.
5. CRITICAL: install EACH package as a SEPARATE task so the report can show
   per-package changed/ok status. Use `name: "Install <package>"` for each.
   - WRONG: one apt task with `name: [pkg1, pkg2, pkg3]` — Ansible marks the
     whole task `changed` if even one package was newly installed, so the
     "Already present" bucket becomes useless.
   - RIGHT: three separate apt tasks, each installing exactly one package.
     Then the report accurately distinguishes truly-new vs already-present.
   Exception: pure setup tasks (apt cache update, repo add) stay as their own
   single tasks — those aren't packages.
6. Call run_playbook(playbook_yaml, host).
7. Read the structured result. To the user, summarize in this exact format:
     Newly installed: <comma-separated list, or "none">
     Already present: <comma-separated list, or "none">
     Failed:          <list with one-line reasons, or "none">

ERROR HANDLING:
- If a task fails because of a wrong package name, missing repo, or distro
  quirk: adapt the playbook (rename pkg, add the repo as a prior task, switch
  module) and retry ONCE. Do not loop endlessly.
- If probe_host fails: stop, return the probe error to the user, and ask them
  to fix inventory / connectivity. Do not try to run a playbook blind.
- "Already present" tasks are SUCCESS, not failure. Ansible reports them as
  ok+unchanged — that is the idempotency working correctly.

SAFETY:
- If the user's request implies destructive ops (rm -rf, dd, mkfs, fdisk,
  dropping databases, deleting users, force-removing packages), STOP and ask
  for explicit confirmation in your response before running.
- If the user's prompt contains "(dry-run)" or "dry run", pass check_mode=true
  to run_playbook and explain that nothing was actually changed.

OUTPUT STYLE: be concise. The user wants to see results, not narration.
"""


async def run_agent(user_request: str, host: str) -> None:
    server = create_sdk_mcp_server(name="vps", version="0.1.0", tools=[probe_host, run_playbook])
    options = ClaudeAgentOptions(
        mcp_servers={"vps": server},
        allowed_tools=["mcp__vps__probe_host", "mcp__vps__run_playbook"],
        system_prompt=SYSTEM_PROMPT,
        max_turns=12,
    )
    prompt = f"Target host (inventory alias): {host}\n\nRequest:\n{user_request}"

    async for message in query(prompt=prompt, options=options):
        # The SDK yields structured messages; print whatever has user-visible text.
        _print_message(message)


def _print_message(message) -> None:
    # The Agent SDK message types vary; fall back to repr for unknown shapes.
    text = getattr(message, "text", None)
    if text:
        print(text)
        return
    content = getattr(message, "content", None)
    if isinstance(content, list):
        for block in content:
            block_text = getattr(block, "text", None) or (block.get("text") if isinstance(block, dict) else None)
            if block_text:
                print(block_text)
        return
    if isinstance(message, (str, bytes)):
        print(message)
        return
    # Unknown message type — quietly skip rather than spam the terminal.


def main_cli() -> None:
    import sys

    if len(sys.argv) < 3:
        print('Usage: python main.py <host_alias> "<natural-language request>"')
        print('Example: python main.py my-linux-vps "install nginx, certbot, ufw"')
        sys.exit(2)

    host = sys.argv[1]
    request = " ".join(sys.argv[2:])

    if not INVENTORY.exists():
        print(f"ERROR: inventory file not found at {INVENTORY}")
        print("Copy inventory/hosts.example.yml to inventory/hosts.yml and edit it.")
        sys.exit(1)

    try:
        asyncio.run(run_agent(request, host))
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
