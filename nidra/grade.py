"""nidra.grade — how a memory earns, and loses, its trust grade.

Two independent checks per evidence row:

1. **Integrity** — does the stored excerpt still match its own sha256?
   A mismatch means the store itself was tampered with or corrupted.
2. **Reality** — does the source still contain the excerpt?
   Absence means the world changed since the memory was verified: the
   memory's grade must fall, no matter how confident it used to be.

Grades: ``unverified`` → ``source_linked`` (evidence recorded, source not
re-checkable right now) → ``machine_checked`` (at least one evidence row
re-verified against its source bytes, none drifted).
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict, List, Tuple

from .store import sha256_text


@lru_cache(maxsize=128)
def _read_source(path: str, mtime_ns: int, size: int) -> str:
    # mtime_ns + size key the cache: a changed file is a different entry.
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _source_content(path: str) -> str:
    st = os.stat(path)
    return _read_source(path, st.st_mtime_ns, st.st_size)


def verify_evidence_row(ev: Dict[str, Any]) -> Tuple[str, str]:
    """Return (state, reason). States: ok | source_missing | drifted | corrupt."""
    excerpt = ev.get("excerpt") or ""
    if sha256_text(excerpt) != ev.get("sha256"):
        return "corrupt", "stored excerpt no longer matches its own sha256"
    source = ev.get("source")
    if not source:
        return "source_missing", "no source recorded"
    if source.startswith(("http://", "https://")):
        return "source_missing", "remote source; the offline pass cannot re-check it"
    if not os.path.exists(source):
        return "source_missing", "source not found: %s" % source
    try:
        content = _source_content(source)
    except OSError as exc:
        return "source_missing", str(exc)
    if excerpt in content:
        return "ok", "excerpt present in source"
    if not excerpt.isascii():
        # ensure_ascii JSONL writers store non-ASCII as \uXXXX escapes; the
        # escaped form is checked too so encoding never masquerades as drift.
        import json as _json

        escaped = _json.dumps(excerpt, ensure_ascii=True)[1:-1]
        if escaped in content:
            return "ok", "excerpt present in source (json-escaped form)"
    return "drifted", "excerpt no longer present in source"


def grade(mem: Dict[str, Any]) -> Tuple[str, List[str], List[str]]:
    """Recompute the evidence grade of one memory.

    Returns (evidence_status, row_states, reasons).
    """
    if not mem.get("evidence"):
        return "unverified", [], ["no evidence rows"]
    states, reasons = [], []
    for ev in mem["evidence"]:
        state, reason = verify_evidence_row(ev)
        states.append(state)
        reasons.append(reason)
    if "corrupt" in states or "drifted" in states:
        return "unverified", states, reasons
    if "ok" in states:
        return "machine_checked", states, reasons
    return "source_linked", states, reasons
