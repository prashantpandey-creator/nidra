"""nidra.report — the trust report: the proof artifact a sleep pass leaves behind."""
from __future__ import annotations

from typing import Any, Dict

STATUS_ORDER = ("machine_checked", "source_linked", "unverified")


def render_markdown(report: Dict[str, Any]) -> str:
    lines = ["# Nidra trust report", "", "Sleep pass at `%s`" % report["started"], ""]
    lines.append("## Census (active memories)")
    lines.append("")
    lines.append("| grade | before | after |")
    lines.append("|---|---:|---:|")
    before, after = report["before"], report["after"]
    for status in STATUS_ORDER:
        lines.append(
            "| %s | %d | %d |"
            % (status, before["by_status"].get(status, 0), after["by_status"].get(status, 0))
        )
    lines.append("| **active total** | %d | %d |" % (before["active"], after["active"]))
    lines.append("| contested | %d | %d |" % (before["contested"], after["contested"]))
    lines.append("")
    lines.append("## Actions (%d)" % len(report["actions"]))
    lines.append("")
    if not report["actions"]:
        lines.append("Nothing to do — the store is already consolidated.")
    for a in report["actions"]:
        lines.append("- **%s** `%s` — %s" % (a["kind"], a["id"], a["detail"]))
    if report["contested"]:
        lines.append("")
        lines.append("## Contested pairs")
        lines.append("")
        for c in report["contested"]:
            lines.append(
                "- (%s, subject `%s`) `%s` %r vs `%s` %r"
                % (
                    c["kind"],
                    c["subject"],
                    c["a"]["id"],
                    c["a"]["statement"],
                    c["b"]["id"],
                    c["b"]["statement"],
                )
            )
    lines.append("")
    return "\n".join(lines)
