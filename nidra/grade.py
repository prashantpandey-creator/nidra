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


_CHUNK = 1 << 20          # 1MB read window


@lru_cache(maxsize=128)
def _read_source(path: str, mtime_ns: int, size: int) -> str:
    # mtime_ns + size key the cache: a changed file is a different entry.
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _source_content(path: str) -> str:
    st = os.stat(path)
    return _read_source(path, st.st_mtime_ns, st.st_size)


@lru_cache(maxsize=4096)
def _source_contains(path: str, mtime_ns: int, size: int, needle: str) -> bool:
    """Is `needle` in this file? Streamed, early-exit, one chunk in memory.

    The old path read the whole source to look for a 200-char excerpt.
    Measured on the live store: 91 evidence rows point at sources over 5MB,
    the largest a 117MB transcript, and a full grade pass took 34.9s —
    `meditate doctor` went from 15s to a >2 minute timeout. Streaming is
    exact for any excerpt (chunks overlap by len(needle)-1, so nothing is
    lost at a seam) and stops at the first hit.
    """
    if not needle:
        return True
    if size <= _CHUNK:                       # small file: keep the shared cache
        return needle in _read_source(path, mtime_ns, size)
    overlap = len(needle) - 1
    tail = ""
    with open(path, encoding="utf-8", errors="replace") as fh:
        while True:
            block = fh.read(_CHUNK)
            if not block:
                return False
            if needle in tail + block:
                return True
            tail = (tail + block)[-overlap:] if overlap else ""


def _source_has(path: str, needle: str) -> bool:
    st = os.stat(path)
    return _source_contains(path, st.st_mtime_ns, st.st_size, needle)


GIT_TIMEOUT_S = 5


@lru_cache(maxsize=512)
def _git_has_commit(repo: str, sha: str) -> str:
    """'yes' | 'no' | 'unknown' — three-valued, and it matters.

    A SHA absent from a repo we CAN read means the commit is gone. A repo we
    cannot read means we do not know — never that the commit is gone. Same
    rule the extractor violated 28 times.

    Verification is fixed-argv git: no shell, so nothing a memory file writes
    can be executed. Memory files are written by agents and re-checked by an
    unattended hourly heartbeat; that is not a place to interpret strings.
    """
    import subprocess

    if not os.path.isdir(os.path.join(repo, ".git")) and not os.path.isdir(repo):
        return "unknown"
    try:
        r = subprocess.run(
            ["git", "-C", repo, "cat-file", "-e", sha + "^{commit}"],
            capture_output=True, timeout=GIT_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if r.returncode == 0:
        return "yes"
    err = (r.stderr or b"").decode("utf-8", "replace").lower()
    # "not a git repository" / "unable to read" are ignorance, not absence.
    if "not a git repo" in err or "unable to read" in err or "detected dubious" in err:
        return "unknown"
    return "no"


def verify_evidence_row(ev: Dict[str, Any]) -> Tuple[str, str]:
    """Return (state, reason). States: ok | source_missing | drifted | corrupt."""
    excerpt = ev.get("excerpt") or ""
    if sha256_text(excerpt) != ev.get("sha256"):
        return "corrupt", "stored excerpt no longer matches its own sha256"
    locator_raw = str(ev.get("locator") or "")
    if locator_raw.startswith("git:") and "@" in locator_raw:
        # The locator may name SEVERAL candidate repos (a memory often spans
        # more than one). Present in any -> ok. Definitely absent from every
        # repo we can READ -> drifted. Nothing readable -> not checkable.
        # CONFIRM-ONLY, and this is the whole design. The repo for a bare SHA
        # is INFERRED from paths in the same memory, so "not found" means we
        # looked in the wrong places at least as often as it means the commit
        # is gone: measured on the live store, 14 of 24 first-pass "drifted"
        # git claims were real commits in a repo the memory never named (58%
        # false). Presence is decidable; absence is not. So this kind can
        # raise confidence and can never manufacture repair work.
        repos_raw, _, sha = locator_raw[4:].rpartition("@")
        repos = [r for r in repos_raw.split("|") if r]
        for r in repos:
            if _git_has_commit(os.path.expanduser(r), sha) == "yes":
                return "ok", "commit %s present in %s" % (sha[:8], r)
        return "source_missing", "commit %s not found in %s — the repo is " \
            "inferred, so this is 'not located', not 'gone'" % (
                sha[:8], ", ".join(repos) or "(no repo)")
    # A path:/wikilink: claim is ABOUT a target's existence, not just about a
    # line being present in the .md. Checking only the excerpt let a claim
    # stay "machine_checked" after its target file was deleted — the dashboard's
    # "still true" was false for the most common claim type. Check the target.
    locator = str(ev.get("locator") or "")
    if locator.startswith("path:"):
        target = os.path.expanduser(locator[5:])
        if not os.path.exists(target):
            return "drifted", "path claim's target no longer exists: %s" % target
    elif locator.startswith("wikilink:") and ev.get("source"):
        if not os.path.exists(ev["source"]):
            return "drifted", "wikilink target memory no longer exists"
    source = ev.get("source")
    if not source:
        return "source_missing", "no source recorded"
    if source.startswith(("http://", "https://")):
        return "source_missing", "remote source; the offline pass cannot re-check it"
    if not os.path.exists(source):
        return "source_missing", "source not found: %s" % source
    try:
        found = _source_has(source, excerpt)
    except OSError as exc:
        return "source_missing", str(exc)
    if found:
        return "ok", "excerpt present in source"
    if not excerpt.isascii():
        # ensure_ascii JSONL writers store non-ASCII as \uXXXX escapes; the
        # escaped form is checked too so encoding never masquerades as drift.
        import json as _json

        escaped = _json.dumps(excerpt, ensure_ascii=True)[1:-1]
        if _source_has(source, escaped):
            return "ok", "excerpt present in source (json-escaped form)"
    return "drifted", "excerpt no longer present in source"


DEFAULT_STORE_ROOTS = (
    os.path.expanduser("~/claude-sync/memory"),
    os.path.expanduser("~/.claude/meditation"),
)

_SCOPE_RANK = {"none": 0, "quote": 1, "internal": 2, "world": 3}


def _row_scope(ev: Dict[str, Any], store_roots: Tuple[str, ...]) -> str:
    """What is THIS row's truth answerable to?

    world    — a referent outside the memory store: a file on disk, a commit.
    internal — another memory file in the same store (wikilinks, and paths
               that point back inside the store). Graph consistency.
    quote    — a content anchor: the memory quotes its own source correctly.
    """
    loc = str(ev.get("locator") or "")
    if loc.startswith("git:"):
        return "world"
    if loc.startswith("path:"):
        p = os.path.expanduser(loc[5:])
        return "internal" if p.startswith(tuple(store_roots)) else "world"
    if loc.startswith("wikilink:"):
        return "internal"
    return "quote"


def evidence_scope(mem: Dict[str, Any],
                   store_roots: Tuple[str, ...] = DEFAULT_STORE_ROOTS) -> str:
    """'world' | 'internal' | 'quote' | 'none' — orthogonal to the grade.

    The grade says how well-checked. This says checked against WHAT, and it
    exists because `machine_checked` hid the difference.

    A wikilink is deliberately NOT world. Its target is another memory file in
    the same store, so resolving it proves the graph is internally consistent
    — precisely the property that can hold while every statement is false.
    Counting wikilinks as world reported 56% of the live store as
    world-decidable; strictly, it is 13%. A metric whose only job is to avoid
    flattering the system must not flatter the system.
    """
    rows = mem.get("evidence") or []
    if not rows:
        return "none"
    return max((_row_scope(ev, store_roots) for ev in rows),
               key=lambda s: _SCOPE_RANK[s])


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
