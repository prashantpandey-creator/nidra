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


# Locator prefixes whose truth is decided BY THE WORLD, not by the memory
# quoting itself correctly. This is the distinction `machine_checked` was
# hiding: measured 2026-08-23, 206 of 483 evidenced memories (43%) were
# quote-only — green, and unfalsifiable by any change in the world.
_WORLD_PREFIXES = ("path:", "wikilink:", "git:")


def evidence_scope(mem: Dict[str, Any]) -> str:
    """'world' | 'quote' | 'none' — orthogonal to the grade, not a rank.

    world: at least one claim the world can refute (a file, a link target, a
           commit). Corroborated.
    quote: only content anchors — proves the memory quotes its source, which
           no external change can ever falsify. Consistent, not corroborated.

    A knowledge base can be perfectly self-consistent and entirely wrong. The
    grade says how well-checked; this says checked against WHAT.
    """
    rows = mem.get("evidence") or []
    if not rows:
        return "none"
    for ev in rows:
        if str(ev.get("locator") or "").startswith(_WORLD_PREFIXES):
            return "world"
    return "quote"


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
