"""Convert Ansible JSON callback output into a structured summary the LLM can reason about."""
from __future__ import annotations

import json
from pathlib import Path


def summarize_run(stdout: str, stderr: str, returncode: int, pb_path: Path) -> str:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return _raw_failure_report(stdout, stderr, returncode, pb_path)

    changed: list[dict] = []
    ok_unchanged: list[dict] = []
    failed: list[dict] = []
    skipped: list[dict] = []
    unreachable: list[dict] = []

    for play in data.get("plays", []):
        for task in play.get("tasks", []):
            tname = task.get("task", {}).get("name") or "<unnamed task>"
            for hostname, res in task.get("hosts", {}).items():
                entry = {"task": tname, "host": hostname}
                if res.get("unreachable"):
                    entry["error"] = res.get("msg") or "host unreachable"
                    unreachable.append(entry)
                elif res.get("failed"):
                    entry["error"] = (
                        res.get("msg")
                        or res.get("stderr")
                        or res.get("stdout")
                        or "(no error message)"
                    )
                    # extract module-specific hints
                    if "module_stderr" in res:
                        entry["error"] += f"\n      module_stderr: {res['module_stderr'][:300]}"
                    failed.append(entry)
                elif res.get("skipped"):
                    entry["reason"] = res.get("skip_reason") or res.get("msg") or ""
                    skipped.append(entry)
                elif res.get("changed"):
                    changed.append(entry)
                else:
                    ok_unchanged.append(entry)

    lines: list[str] = []
    lines.append(f"Playbook: {pb_path.name}  (rc={returncode})")
    lines.append("")

    lines.append(f"CHANGED ({len(changed)}):")
    for e in changed:
        lines.append(f"  - {e['task']} on {e['host']}")
    if not changed:
        lines.append("  (none)")

    lines.append("")
    lines.append(f"ALREADY IN DESIRED STATE / OK ({len(ok_unchanged)}):")
    for e in ok_unchanged:
        lines.append(f"  - {e['task']} on {e['host']}  (no change needed)")
    if not ok_unchanged:
        lines.append("  (none)")

    if skipped:
        lines.append("")
        lines.append(f"SKIPPED ({len(skipped)}):")
        for e in skipped:
            lines.append(f"  - {e['task']} on {e['host']}  ({e.get('reason','')})")

    if unreachable:
        lines.append("")
        lines.append(f"UNREACHABLE ({len(unreachable)}):")
        for e in unreachable:
            lines.append(f"  - {e['host']}: {e['error']}")

    if failed:
        lines.append("")
        lines.append(f"FAILED ({len(failed)}):")
        for e in failed:
            lines.append(f"  - {e['task']} on {e['host']}")
            err = str(e.get("error", "")).strip().replace("\n", "\n      ")
            lines.append(f"      reason: {err}")

    if stderr.strip() and not failed and not unreachable:
        lines.append("")
        lines.append(f"STDERR (warnings):\n{stderr.strip()[:1000]}")

    return "\n".join(lines)


def _raw_failure_report(stdout: str, stderr: str, returncode: int, pb_path: Path) -> str:
    return (
        f"Playbook execution returned non-JSON output (rc={returncode}).\n"
        f"This usually means Ansible failed before any play started "
        f"(syntax error, inventory error, auth refused, etc.).\n\n"
        f"Playbook saved at: {pb_path}\n\n"
        f"STDOUT (first 3000 chars):\n{stdout[:3000]}\n\n"
        f"STDERR (first 2000 chars):\n{stderr[:2000]}"
    )
