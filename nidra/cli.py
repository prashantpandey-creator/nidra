"""nidra CLI — init, add, sleep, why, report, demo.

``nidra demo`` is the proof command: it plants a store with known defects,
runs two sleep passes (the world changes between them), and verifies that
every planted defect was caught. ``--strict`` exits non-zero on any miss —
CI runs exactly that, so the badge on the README is the ongoing proof.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone

from .grade import verify_evidence_row
from .judge import AnthropicJudge
from .report import render_markdown
from .sleep import run_sleep
from .store import Store, new_memory


def _store(args) -> Store:
    return Store(args.dir)


def cmd_init(args) -> int:
    store = _store(args)
    store.init()
    print("initialized palace at %s" % store.root)
    return 0


def cmd_add(args) -> int:
    store = _store(args)
    if not store.exists():
        store.init()
    mem = new_memory(
        args.statement,
        subject=args.subject,
        source=args.source,
        excerpt=args.excerpt,
        locator=args.locator,
    )
    stored = store.add(mem)
    print(stored["id"])
    return 0


def cmd_sleep(args) -> int:
    store = _store(args)
    judge = AnthropicJudge(model=args.judge_model) if args.judge else None
    report = run_sleep(store, judge=judge)
    md = render_markdown(report)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            fh.write(md)
        print("report written to %s" % args.report)
    else:
        print(md)
    return 0


def cmd_why(args) -> int:
    store = _store(args)
    mem = store.get(args.id)
    if mem is None:
        print("no memory %s" % args.id, file=sys.stderr)
        return 1
    print(json.dumps(mem, indent=2, ensure_ascii=False))
    print("\nevidence re-check, right now:")
    if not mem["evidence"]:
        print("  (no evidence rows — this memory has no receipts)")
    for ev in mem["evidence"]:
        state, reason = verify_evidence_row(ev)
        print("  [%s] %s — %s" % (state, ev["source"], reason))
    events = store.journal_for(args.id)
    if events:
        print("\njournal:")
        for e in events:
            print("  %s %s %s" % (e.get("ts", ""), e.get("event", ""), e.get("detail", "")))
    return 0


def run_demo(root: str, strict: bool = False, quiet: bool = False) -> int:
    """Plant known defects, sleep twice, verify every defect was caught."""

    def say(msg: str) -> None:
        if not quiet:
            print(msg)

    if os.path.exists(root):
        shutil.rmtree(root)
    sources = os.path.join(root, "sources")
    os.makedirs(sources)
    store = Store(os.path.join(root, "palace"))
    store.init()

    deploy_md = os.path.join(sources, "deploy.md")
    retry_md = os.path.join(sources, "retry.md")
    with open(deploy_md, "w") as fh:
        fh.write("# Deploy notes\nThe service runs on port 8000 behind nginx.\n")
    with open(retry_md, "w") as fh:
        fh.write("# Client config\nThe retry limit is 5 for all outbound calls.\n")

    old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    plans = [
        new_memory(
            "The service runs on port 8000",
            subject="service-port",
            source=deploy_md,
            excerpt="runs on port 8000",
        ),
        new_memory("Redis cache TTL is seven days", subject="redis-ttl"),
        new_memory("redis cache TTL is SEVEN days!!", subject="redis-ttl"),
        new_memory(
            "The retry limit is 5",
            subject="retry-limit",
            source=retry_md,
            excerpt="retry limit is 5",
        ),
        new_memory("The gateway timeout is 30 seconds", subject="gateway-timeout"),
        new_memory("The gateway timeout is 60 seconds", subject="gateway-timeout"),
        new_memory("Telemetry is enabled in production", subject="telemetry"),
        new_memory("Telemetry is not enabled in production", subject="telemetry"),
        new_memory("maybe that cron thing was flaky once", confidence=0.3, now=old),
    ]
    # The second redis note arrives under a foreign id, as an import from
    # another store would — content-addressed ids already absorb exact re-adds,
    # so the dedup stage exists precisely for imported duplicates like this one.
    plans[2]["id"] = "mem_imported_dup"
    for mem in plans:
        store.add(mem)

    say("Planted %d memories with 5 known defects. Night one:" % len(plans))
    night1 = run_sleep(store)
    say(render_markdown(night1))

    # The world changes: the retry limit is raised in the source of truth.
    with open(retry_md, "w") as fh:
        fh.write("# Client config\nThe retry limit is 6 for all outbound calls.\n")
    say("The world changed (retry limit 5 -> 6 in the source). Night two:")
    night2 = run_sleep(store)
    say(render_markdown(night2))

    kinds1 = [a["kind"] for a in night1["actions"]]
    kinds2 = [a["kind"] for a in night2["actions"]]
    port_mem = store.get(plans[0]["id"])
    retry_mem = store.get(plans[3]["id"])
    checks = [
        ("duplicate pair merged", kinds1.count("merged") == 1),
        (
            "good memory promoted to machine_checked",
            port_mem is not None
            and port_mem["epistemic"]["evidence_status"] == "machine_checked",
        ),
        ("numeric + negation contradictions flagged", len(night1["contested"]) >= 2),
        ("overdue junk tombstoned", "tombstoned" in kinds1),
        (
            "stale verified memory demoted after source change",
            "demoted" in kinds2
            and retry_mem is not None
            and retry_mem["epistemic"]["evidence_status"] == "unverified"
            and "drifted" in retry_mem["flags"],
        ),
        ("third pass is a no-op (idempotent)", not run_sleep(store)["actions"]),
    ]
    say("Proof:")
    failed = 0
    for label, ok in checks:
        say("  [%s] %s" % ("PASS" if ok else "FAIL", label))
        if not ok:
            failed += 1
    if failed:
        say("%d planted defect(s) NOT caught" % failed)
        return 1 if strict else 0
    say("All planted defects caught. The pass proves itself.")
    return 0


def cmd_import_mempalace(args) -> int:
    from .adapters.mempalace import import_palace

    store = _store(args)
    if not store.exists():
        store.init()
    summary = import_palace(
        store, palace=args.palace, wing=args.wing, room=args.room, limit=args.limit
    )
    print(json.dumps(summary, indent=2))
    return 0


def cmd_demo(args) -> int:
    return run_demo(args.dir, strict=args.strict)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="nidra", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create a palace directory")
    p.add_argument("--dir", default=".nidra")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("add", help="add a memory (optionally with evidence)")
    p.add_argument("statement")
    p.add_argument("--dir", default=".nidra")
    p.add_argument("--subject")
    p.add_argument("--source", help="file the evidence excerpt lives in")
    p.add_argument("--excerpt", help="the exact supporting text from the source")
    p.add_argument("--locator", help="where in the source (line, section, timestamp)")
    p.set_defaults(fn=cmd_add)

    p = sub.add_parser("sleep", help="run the consolidation pass")
    p.add_argument("--dir", default=".nidra")
    p.add_argument("--report", help="write the trust report to this markdown file")
    p.add_argument("--judge", action="store_true", help="resolve contested pairs with an LLM")
    p.add_argument("--judge-model", default="claude-haiku-4-5")
    p.set_defaults(fn=cmd_sleep)

    p = sub.add_parser("why", help="show a memory with its receipts, re-checked live")
    p.add_argument("id")
    p.add_argument("--dir", default=".nidra")
    p.set_defaults(fn=cmd_why)

    p = sub.add_parser(
        "import-mempalace",
        help="import MemPalace drawers as graded memories (palace is read-only)",
    )
    p.add_argument("--dir", default=".nidra")
    p.add_argument("--palace", default="~/.mempalace")
    p.add_argument("--wing")
    p.add_argument("--room")
    p.add_argument("--limit", type=int)
    p.set_defaults(fn=cmd_import_mempalace)

    p = sub.add_parser("demo", help="plant known defects and prove the pass catches them")
    p.add_argument("--dir", default=".nidra-demo")
    p.add_argument("--strict", action="store_true", help="exit non-zero if any defect is missed")
    p.set_defaults(fn=cmd_demo)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
