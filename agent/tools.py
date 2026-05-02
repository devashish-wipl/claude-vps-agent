"""Custom tools the Claude agent uses to drive Ansible."""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path

from .parsing import summarize_run

ANSIBLE_BIN = os.environ.get("ANSIBLE_BIN", "ansible")
ANSIBLE_PLAYBOOK_BIN = os.environ.get("ANSIBLE_PLAYBOOK_BIN", "ansible-playbook")


async def _run(cmd: list[str], env_extra: dict | None = None) -> tuple[int, str, str]:
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout_b, stderr_b = await proc.communicate()
    return (
        proc.returncode if proc.returncode is not None else -1,
        stdout_b.decode(errors="replace"),
        stderr_b.decode(errors="replace"),
    )


async def probe_host_impl(host: str, inventory: Path) -> str:
    """Run `ansible -m setup` to discover OS facts for the target host."""
    code, out, err = await _run([
        ANSIBLE_BIN,
        host,
        "-i", str(inventory),
        "-m", "setup",
        "-a", "filter=ansible_distribution*,ansible_os_family,ansible_pkg_mgr,ansible_system,ansible_architecture",
    ])
    if code != 0:
        return (
            f"PROBE FAILED for host='{host}' (rc={code}).\n"
            f"stderr: {err.strip()[:1500]}\n"
            f"stdout: {out.strip()[:500]}\n\n"
            f"Common causes: host alias missing in inventory, SSH key not authorized, "
            f"WinRM disabled on Windows target, host unreachable. Verify with:\n"
            f"  ansible {host} -i {inventory} -m ping"
        )

    # ansible -m setup prints "<host> | SUCCESS => { json }"
    try:
        brace = out.index("{")
        facts = json.loads(out[brace:])
        af = facts.get("ansible_facts", {})
        return json.dumps(
            {
                "system": af.get("ansible_system"),
                "os_family": af.get("ansible_os_family"),
                "distribution": af.get("ansible_distribution"),
                "version": af.get("ansible_distribution_version"),
                "pkg_mgr": af.get("ansible_pkg_mgr"),
                "architecture": af.get("ansible_architecture"),
            },
            indent=2,
        )
    except (ValueError, json.JSONDecodeError) as e:
        return f"Probe succeeded but failed to parse facts: {e}\nRaw (first 2000 chars):\n{out[:2000]}"


async def run_playbook_impl(
    yaml_content: str,
    host: str,
    inventory: Path,
    playbook_dir: Path,
    check_mode: bool = False,
) -> str:
    """Save and run an Ansible playbook against a single host. Returns a structured summary."""
    pb_path = playbook_dir / f"play_{uuid.uuid4().hex[:8]}.yml"
    pb_path.write_text(yaml_content)

    cmd = [ANSIBLE_PLAYBOOK_BIN, str(pb_path), "-i", str(inventory), "-l", host]
    if check_mode:
        cmd.append("--check")

    code, out, err = await _run(
        cmd,
        env_extra={
            "ANSIBLE_STDOUT_CALLBACK": "json",
            "ANSIBLE_LOAD_CALLBACK_PLUGINS": "1",
            "ANSIBLE_HOST_KEY_CHECKING": "False",
        },
    )
    return summarize_run(out, err, code, pb_path)
