"""nidra.adapters.meditate — import meditate session maps into nidra.

Meditate's sessions.py parses Claude Code transcripts into compact maps.
This adapter converts those maps into nidra memories with evidence receipts
pointing back at the raw transcript JSONL — so drift detection applies to
session-level facts the same way it applies to scripture answers.

Evidence: the first user message text from the session. It lives in the
transcript as a JSON-encoded ``message.content`` string, so the anchor is
chosen with the same escape-proof discipline as the mempalace adapter.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from ..store import Store, new_memory, sha256_text
from .mempalace import clean_anchor

SESSION_TAG = "meditate-session"
STATEMENT_CAP = 600


def session_to_memory(
    session: Dict[str, Any],
    transcript_path: Optional[str] = None,
) -> Dict[str, Any]:
    sid = session.get("session_id", "unknown")
    title = session.get("title") or "(untitled)"
    projects = ", ".join(session.get("projects", [])[:3]) or "unknown"
    n_user = session.get("counts", {}).get("user", 0)
    n_files = len(session.get("files_touched", []))
    sprawl = session.get("sprawl_score", 0)

    statement = (
        f"Session '{title}' on {projects}. "
        f"{n_user} turns, {n_files} files, sprawl {sprawl}."
    )
    chapters = session.get("chapter_marks", [])
    if chapters:
        chapter_text = "; ".join(c.get("title", "?") for c in chapters[:10])
        statement += f" Chapters: {chapter_text}."
    if len(statement) > STATEMENT_CAP:
        statement = statement[:STATEMENT_CAP] + "…"

    tags = [SESSION_TAG]
    for p in session.get("projects", [])[:5]:
        tags.append(f"project:{p}")

    first_user = session.get("first_user")
    anchor = clean_anchor(first_user) if first_user else None
    source = transcript_path or session.get("file")

    mem = new_memory(
        statement,
        subject=f"session:{sid}",
        source=source if anchor else None,
        excerpt=anchor if source else None,
        locator=sid,
        tags=tags,
        now=session.get("ts_start"),
    )
    mem["id"] = "mem_" + sha256_text("session|" + sid)[:12]
    return mem


def import_sessions(
    store: Store,
    sessions: List[Dict[str, Any]],
    project_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Bulk-import session maps into nidra. Idempotent."""
    existing = {m["id"]: m for m in store.load()}
    summary = {
        "scanned": 0,
        "imported": 0,
        "already_exists": 0,
        "no_anchor": 0,
    }
    fresh: Dict[str, Dict[str, Any]] = {}

    for session in sessions:
        summary["scanned"] += 1
        transcript_path = None
        if project_dir and session.get("file"):
            transcript_path = os.path.join(project_dir, session["file"])

        mem = session_to_memory(session, transcript_path)

        if not mem.get("evidence"):
            summary["no_anchor"] += 1
            # No turns AND no anchor: an empty transcript, not a session
            # anyone had. Its statement holds no claim, so it can never be
            # verified — it just sits `unverified` forever and drowns the
            # real drift signal in the census. A session WITH turns but no
            # anchor still imports; it has content, it just can't be pinned.
            if not session.get("counts", {}).get("user", 0):
                continue

        if mem["id"] in existing or mem["id"] in fresh:
            summary["already_exists"] += 1
            continue

        fresh[mem["id"]] = mem
        summary["imported"] += 1

    mems = list(existing.values()) + list(fresh.values())
    store.save(mems)
    store.journal({
        "event": "import.meditate",
        "project_dir": project_dir,
        "scanned": summary["scanned"],
        "imported": summary["imported"],
    })
    return summary
