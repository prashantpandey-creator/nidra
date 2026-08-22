"""Tests for nidra.adapters.meditate (Rule 0, precondition A).

Run: cd /Users/badenath/projects/nidra && python -m pytest -q tests/test_meditate_adapter.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from nidra.adapters.meditate import session_to_memory, import_sessions
from nidra.store import Store


FIXTURE = {
    "session_id": "abc123",
    "file": "abc123.jsonl",
    "title": "Drift detection deep dive",
    "cwd": "/Users/test/projects/nidra",
    "git_branch": "main",
    "size_bytes": 524288,
    "ts_start": "2026-08-20T10:00:00Z",
    "ts_end": "2026-08-20T12:30:00Z",
    "counts": {"user": 15, "assistant": 14},
    "first_user": "explain how drift detection works in the recall cache layer",
    "last_user": "build the three pipes",
    "user_messages": [
        {"ts": "2026-08-20T10:00:00Z", "text": "explain how drift detection works"},
    ],
    "chapter_marks": [
        {"ts": "2026-08-20T10:30:00Z", "title": "Nidra drift detection"},
        {"ts": "2026-08-20T11:00:00Z", "title": "Building the three pipes"},
    ],
    "files_touched": [
        "/Users/test/projects/nidra/nidra/recall.py",
        "/Users/test/projects/nidra/nidra/grade.py",
    ],
    "projects": ["nidra"],
    "top_tools": [["Read", 12], ["Bash", 8]],
    "sprawl_score": 4.1,
}


def test_memory_shape():
    mem = session_to_memory(FIXTURE, "/tmp/abc123.jsonl")
    assert mem["id"].startswith("mem_")
    assert mem["subject"] == "session:abc123"
    assert "meditate-session" in mem["tags"]
    assert "project:nidra" in mem["tags"]
    assert mem["active"] is True


def test_evidence_receipt():
    mem = session_to_memory(FIXTURE, "/tmp/abc123.jsonl")
    assert len(mem["evidence"]) == 1
    ev = mem["evidence"][0]
    assert ev["source"] == "/tmp/abc123.jsonl"
    assert ev["sha256"]
    assert ev["excerpt"]


def test_no_evidence_without_first_user():
    session = dict(FIXTURE, first_user=None)
    mem = session_to_memory(session, "/tmp/abc123.jsonl")
    assert len(mem["evidence"]) == 0


def test_chapters_in_statement():
    mem = session_to_memory(FIXTURE, "/tmp/abc123.jsonl")
    assert "Nidra drift detection" in mem["statement"]
    assert "Building the three pipes" in mem["statement"]


def test_statement_captures_project():
    mem = session_to_memory(FIXTURE)
    assert "nidra" in mem["statement"]


def test_import_idempotent():
    with tempfile.TemporaryDirectory() as d:
        store = Store(d)
        store.init()
        r1 = import_sessions(store, [FIXTURE])
        assert r1["imported"] == 1
        assert r1["already_exists"] == 0
        r2 = import_sessions(store, [FIXTURE])
        assert r2["imported"] == 0
        assert r2["already_exists"] == 1
        assert len(store.load()) == 1


def test_import_multiple():
    s2 = dict(FIXTURE, session_id="def456", title="Second session",
              first_user="some completely different user message for this other session")
    with tempfile.TemporaryDirectory() as d:
        store = Store(d)
        store.init()
        r = import_sessions(store, [FIXTURE, s2])
        assert r["scanned"] == 2
        assert r["imported"] == 2
        assert len(store.load()) == 2


def test_no_anchor_counted():
    session = dict(FIXTURE, first_user="hi")  # too short for anchor
    with tempfile.TemporaryDirectory() as d:
        store = Store(d)
        store.init()
        r = import_sessions(store, [session])
        assert r["no_anchor"] == 1
        assert r["imported"] == 1  # still imports, just unverified


def test_empty_transcripts_are_not_imported():
    """0 user turns AND no anchor = an empty file, not a session anyone had.

    Its statement carries no claim, so it can never be verified and sits
    `unverified` forever — 3 of the 5 remaining unverified memories on the
    real store were "Session '(untitled)' on unknown. 0 turns, 0 files".
    A session with turns but no anchor (test_no_anchor_counted) still
    imports: it has real content, it just can't be anchored.
    """
    with tempfile.TemporaryDirectory() as d:
        store = Store(d); store.init()
        empty = {"session_id": "e1", "file": "e1.jsonl", "counts": {"user": 0},
                 "files_touched": [], "sprawl_score": 0.0}
        r = import_sessions(store, [empty, FIXTURE])
        assert r["scanned"] == 2, r
        assert r["imported"] == 1, "imported an empty transcript: %s" % r
        assert [m["subject"] for m in store.load()] == ["session:" + FIXTURE["session_id"]]


def test_statement_refreshes_when_the_session_map_improves():
    """A session memory's statement is DERIVED — re-derive it.

    Import deduped by id and never touched the existing row, so when the
    title parser was fixed, 90 of 111 stored session memories kept saying
    "Session '(untitled)' on unknown" forever. Re-import must refresh what
    it derives, while still reporting the memory as already-existing.
    """
    with tempfile.TemporaryDirectory() as d:
        store = Store(d); store.init()
        before = dict(FIXTURE, title=None)
        import_sessions(store, [before])
        assert "(untitled)" in store.load()[0]["statement"]

        after = dict(FIXTURE, title="Fix the retry loop")
        r = import_sessions(store, [after])
        assert r["imported"] == 0 and r["already_exists"] == 1, r
        mems = store.load()
        assert len(mems) == 1, "refresh must not duplicate the memory"
        assert "Fix the retry loop" in mems[0]["statement"], mems[0]["statement"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {fn.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"  ERR  {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
