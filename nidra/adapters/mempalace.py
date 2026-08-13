"""nidra.adapters.mempalace — grade a MemPalace against its own sources.

MemPalace (https://github.com/MemPalace/mempalace) mines conversations into a
ChromaDB "palace": drawer text lives in ``chroma.sqlite3`` under the
``mempalace_drawers`` collection, with per-drawer metadata (``source_file``,
``wing``, ``room``, ``filed_at``, ``line_start``/``line_end``).

This adapter reads the palace **strictly read-only** (SQLite ``mode=ro``) and
converts drawers into Nidra memories whose evidence points back at the original
transcript bytes:

- statement  = the drawer's verbatim text (capped for readability)
- evidence   = source_file + a *clean anchor* excerpt + sha256
- locator    = the drawer id (plus line range when recorded)

**Clean anchor.** Transcript sources are JSONL, so drawer text appears there
JSON-escaped. A substring containing ``"``, ``\\`` or newlines will never match
the raw bytes even when the memory is faithful — so the anchor is the longest
escape-free run of the drawer text. Drawers with no adequate anchor are imported
*without* evidence and honestly graded ``unverified`` rather than given a
receipt that could never verify.

The palace is never written. Nidra's store is the single writer of its own
files, and the import is bulk (one load, one save, one journal event) and
idempotent: re-importing the same drawers adds nothing.
"""
from __future__ import annotations

import os
import re
import sqlite3
from typing import Any, Dict, Iterator, List, Optional, Tuple

from ..store import Store, new_memory, sha256_text

DRAWERS_COLLECTION = "mempalace_drawers"
STATEMENT_CAP = 1200
ANCHOR_MIN = 24
ANCHOR_MAX = 160

# Printable ASCII except `"` and `\\` — the exact set every JSONL writer emits
# verbatim, whether or not it escapes non-ASCII (ensure_ascii both ways).
_ANCHOR_RUN = re.compile(r"[ -!#-\[\]-~]+")
# MemPalace decorates drawer text with quote/list prefixes that are NOT in the
# source bytes; strip them per line before choosing an anchor.
_RENDER_PREFIX = re.compile(r"^[>*#\s-]+")


def clean_anchor(text: str, min_len: int = ANCHOR_MIN, max_len: int = ANCHOR_MAX) -> Optional[str]:
    """Longest escaping-proof run of the text, else None.

    An anchor must fail re-verification only when the *source* changed — never
    because of encoding. So anchors are pure printable ASCII (immune to
    ensure_ascii variance) with rendering prefixes stripped (not source bytes).
    """
    best = ""
    for line in (text or "").splitlines():
        line = _RENDER_PREFIX.sub("", line)
        for run in _ANCHOR_RUN.findall(line):
            run = run.strip()
            if len(run) > len(best):
                best = run
    if len(best) < min_len:
        return None
    return best[:max_len].strip()


def _connect(palace: str) -> sqlite3.Connection:
    db_path = os.path.join(os.path.expanduser(palace), "palace", "chroma.sqlite3")
    if not os.path.exists(db_path):
        raise FileNotFoundError("no MemPalace chroma.sqlite3 at %s" % db_path)
    return sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)


def iter_drawers(
    palace: str,
    wing: Optional[str] = None,
    room: Optional[str] = None,
    limit: Optional[int] = None,
) -> Iterator[Dict[str, Any]]:
    """Yield drawers as flat dicts: {drawer_id, document, <metadata...>}."""
    db = _connect(palace)
    try:
        cur = db.cursor()
        where, params = [], []
        for key, value in (("wing", wing), ("room", room)):
            if value is not None:
                where.append(
                    "e.id IN (SELECT id FROM embedding_metadata "
                    "WHERE key=? AND string_value=?)"
                )
                params.extend([key, value])
        seg = cur.execute(
            "SELECT s.id FROM segments s JOIN collections c ON s.collection=c.id "
            "WHERE c.name=? AND s.scope='METADATA'",
            (DRAWERS_COLLECTION,),
        ).fetchone()
        sql = "SELECT e.id, e.embedding_id FROM embeddings e"
        if seg:
            where.append("e.segment_id=?")
            params.append(seg[0])
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY e.id"
        if limit:
            sql += " LIMIT %d" % int(limit)
        rows = cur.execute(sql, params).fetchall()
        for chunk_start in range(0, len(rows), 500):
            chunk = rows[chunk_start : chunk_start + 500]
            ids = [r[0] for r in chunk]
            names = {r[0]: r[1] for r in chunk}
            meta: Dict[int, Dict[str, Any]] = {i: {} for i in ids}
            marks = ",".join("?" * len(ids))
            for mid, key, sv, iv, fv in cur.execute(
                "SELECT id, key, string_value, int_value, float_value "
                "FROM embedding_metadata WHERE id IN (%s)" % marks,
                ids,
            ):
                meta[mid][key] = sv if sv is not None else (iv if iv is not None else fv)
            for i in ids:
                m = meta[i]
                doc = m.pop("chroma:document", None)
                if not doc:
                    continue
                m["drawer_id"] = names[i]
                m["document"] = doc
                yield m
    finally:
        db.close()


def drawer_to_memory(drawer: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """Convert one drawer. Returns (memory, has_verifiable_anchor)."""
    doc = drawer["document"]
    statement = doc if len(doc) <= STATEMENT_CAP else doc[:STATEMENT_CAP] + " …"
    tags = [
        "mempalace",
        "wing:%s" % drawer.get("wing", "?"),
        "room:%s" % drawer.get("room", "?"),
    ]
    anchor = clean_anchor(doc)
    source = drawer.get("source_file")
    locator = drawer.get("drawer_id", "")
    if drawer.get("line_start") is not None:
        locator += " L%s-%s" % (drawer.get("line_start"), drawer.get("line_end"))
    filed_at = drawer.get("filed_at")
    mem = new_memory(
        statement,
        subject=None,
        source=source if anchor else None,
        excerpt=anchor if source else None,
        locator=locator,
        tags=tags,
        now=filed_at,
    )
    return mem, bool(anchor and source)


def import_palace(
    store: Store,
    palace: str = "~/.mempalace",
    wing: Optional[str] = None,
    room: Optional[str] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Bulk-import drawers into the store. One load, one save, one journal event."""
    existing = {m["id"]: m for m in store.load()}
    summary = {
        "scanned": 0,
        "imported": 0,
        "merged_existing": 0,
        "duplicate_text": 0,
        "no_anchor": 0,
        "rooms": {},
    }
    fresh: Dict[str, Dict[str, Any]] = {}
    for drawer in iter_drawers(palace, wing=wing, room=room, limit=limit):
        summary["scanned"] += 1
        room_name = str(drawer.get("room", "?"))
        summary["rooms"][room_name] = summary["rooms"].get(room_name, 0) + 1
        mem, has_anchor = drawer_to_memory(drawer)
        if not has_anchor:
            summary["no_anchor"] += 1
        target = existing.get(mem["id"]) or fresh.get(mem["id"])
        if target is not None:
            seen = {(e["source"], e["excerpt"]) for e in target["evidence"]}
            for ev in mem["evidence"]:
                if (ev["source"], ev["excerpt"]) not in seen:
                    target["evidence"].append(ev)
            if mem["id"] in existing:
                summary["merged_existing"] += 1
            else:
                summary["duplicate_text"] += 1
            continue
        fresh[mem["id"]] = mem
        summary["imported"] += 1
    mems = list(existing.values()) + list(fresh.values())
    store.save(mems)
    store.journal(
        {
            "event": "import.mempalace",
            "palace": os.path.expanduser(palace),
            "wing": wing,
            "room": room,
            "scanned": summary["scanned"],
            "imported": summary["imported"],
        }
    )
    return summary
