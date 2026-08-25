"""Bi-temporal: separate WHEN A FACT WAS TRUE from WHEN WE CHECKED IT.

The store already had transaction time — ``last_reviewed`` and ``review_due``
say when *we* looked. It had no valid time, so a memory that correctly records
a fact with a closed window ("the timeout was 30s during the June pilot") got
demoted in August for evidence that no longer matches. The memory is not
wrong. The window closed.

This is the general form of a bug already fixed once in the special case:
memories that state an absence ("the plan file is gone") were marked drifted
for being correct. That fix patched one shape. Valid time covers the class.

The rule for ``valid_until`` is Graphiti issue #1489's, arrived at
independently there and here: **null by default**. Only a memory that
explicitly states its own end gets a closing timestamp. Never infer one from
"today", because an inferred end date silently retires facts that are still
in force.

Orthogonality matters and is pinned below: ``in_force`` is NOT a fourth
``evidence_status``. Grade answers "how well checked", scope answers "checked
against what", force answers "is this still in effect". Collapsing any two of
those is what produced the 56%-vs-13% scope error.
"""
from __future__ import annotations

import datetime as _dt

from nidra.grade import grade, in_force
from nidra.sleep import run_sleep
from nidra.store import Store, new_memory


def _iso(days: int) -> str:
    return (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(days=days)).isoformat()


# --------------------------------------------------------------------------
# the field itself
# --------------------------------------------------------------------------

def test_new_memory_has_valid_time_and_it_is_open_by_default():
    m = new_memory("the timeout is 30s")
    t = m["temporal"]
    assert "valid_from" in t and "valid_until" in t
    assert t["valid_until"] is None, "a new fact must not be born with an end date"
    assert t["valid_from"] == t["recorded_at"], "default valid_from is when we learned it"


def test_transaction_time_and_valid_time_are_independent():
    """Ingesting an old fact today: learned now, true since June."""
    m = new_memory("the pilot used a 30s timeout")
    m["temporal"]["valid_from"] = "2026-06-01T00:00:00+00:00"
    m["temporal"]["valid_until"] = "2026-06-30T00:00:00+00:00"
    assert m["temporal"]["recorded_at"] > m["temporal"]["valid_from"]
    assert in_force(m) is False


# --------------------------------------------------------------------------
# in_force: the predicate
# --------------------------------------------------------------------------

def test_open_window_is_in_force():
    assert in_force(new_memory("x")) is True


def test_future_end_date_is_still_in_force():
    m = new_memory("x")
    m["temporal"]["valid_until"] = _iso(30)
    assert in_force(m) is True


def test_past_end_date_is_not_in_force():
    m = new_memory("x")
    m["temporal"]["valid_until"] = _iso(-1)
    assert in_force(m) is False


def test_not_yet_started_is_not_in_force():
    m = new_memory("x")
    m["temporal"]["valid_from"] = _iso(30)
    assert in_force(m) is False


def test_unparseable_timestamp_is_in_force_not_expired():
    """Three-valued discipline: 'I cannot read this' must not mean 'expired'.

    A checker that cannot say "I don't know" says "broken" instead. That
    mistake, at six different altitudes, is most of this repo's bug history.
    """
    for junk in ("not-a-date", "", "2026-13-45", None, 12345, [], {}):
        m = new_memory("x")
        m["temporal"]["valid_until"] = junk
        assert in_force(m) is True, "unreadable end date wrongly retired the memory: %r" % (junk,)


def test_memory_with_no_temporal_block_at_all_is_in_force():
    """632 memories already on disk predate this field. None may break."""
    assert in_force({"statement": "x"}) is True
    assert in_force({"statement": "x", "temporal": {}}) is True
    assert in_force({"statement": "x", "temporal": None}) is True


# --------------------------------------------------------------------------
# the point: an expired memory is not a drifted memory
# --------------------------------------------------------------------------

def _drifting(tmp_path, statement="the client timeout is 30 seconds"):
    src = tmp_path / "config.py"
    src.write_text("TIMEOUT = 30\n")
    m = new_memory(statement, source=str(src), excerpt="TIMEOUT = 30",
                   locator="path:%s" % src)
    return m, src


def test_open_window_still_demotes_on_drift(tmp_path):
    """No regression: the ordinary case must behave exactly as before."""
    m, src = _drifting(tmp_path)
    assert grade(m)[0] == "machine_checked"
    src.write_text("TIMEOUT = 90\n")
    assert grade(m)[0] == "unverified"


def test_closed_window_is_not_demoted_when_the_world_moves_on(tmp_path):
    """The whole reason this file exists — over the real lifecycle.

    Earn the grade while the fact is live, THEN close the window, THEN let the
    world move. An expired memory keeps what it earned; it is not handed a
    grade it never had (a memory that expired before anyone checked it stays
    ``unverified``, which is the honest answer and is pinned separately).
    """
    m, src = _drifting(tmp_path, "the June pilot used a 30s timeout")
    status, _, _ = grade(m)
    assert status == "machine_checked"
    m["epistemic"]["evidence_status"] = status   # what a sleep pass persists

    m["temporal"]["valid_until"] = _iso(-1)      # the window closed yesterday
    src.write_text("TIMEOUT = 90\n")             # the world moved on

    status, states, reasons = grade(m)
    assert status == "machine_checked", "a fact with a closed window was demoted for being history"
    assert "drifted" not in states
    assert any("valid" in r for r in reasons)


def test_expired_before_ever_being_checked_keeps_unverified(tmp_path):
    """The falsifier for the rule above: it holds the earned grade, and an
    unchecked memory earned nothing. Inventing ``machine_checked`` here would
    be the tool flattering itself, which is the failure mode it exists to
    prevent."""
    m, _ = _drifting(tmp_path)
    m["temporal"]["valid_until"] = _iso(-1)
    assert grade(m)[0] == "unverified"


def test_sleep_pass_does_not_flag_an_expired_memory_as_drifted(tmp_path):
    """End to end, through run_sleep — grade() alone passing is not enough."""
    store = Store(str(tmp_path / "store"))
    store.init()
    m, src = _drifting(tmp_path)
    store.save([m])

    run_sleep(store)                              # earns machine_checked while live
    assert store.load()[0]["epistemic"]["evidence_status"] == "machine_checked"

    m = store.load()[0]
    m["temporal"]["valid_until"] = _iso(-1)       # window closes
    store.save([m])
    src.write_text("TIMEOUT = 90\n")              # world moves on

    run_sleep(store)
    got = store.load()[0]
    assert "drifted" not in (got["flags"] or []), "expired memory entered the repair queue"
    assert got["epistemic"]["evidence_status"] == "machine_checked"
    assert got["epistemic"]["confidence"] >= 0.9, "expired memory was confidence-penalised"


def test_expired_memory_still_reports_its_scope(tmp_path):
    """Skipping the drift check must not skip the orthogonal bookkeeping."""
    store = Store(str(tmp_path / "store"))
    store.init()
    m, _ = _drifting(tmp_path)
    m["temporal"]["valid_until"] = _iso(-1)
    store.save([m])
    run_sleep(store)
    assert store.load()[0]["epistemic"]["evidence_scope"] == "world"


def test_replay_reads_valid_time_at_the_REPLAYED_instant(tmp_path):
    """run_sleep must have ONE clock.

    The first cut of this feature threaded ``now`` through review scheduling
    and prune, but read valid time off the wall clock. So replaying a backfill
    at a date when the window was WIDE OPEN still skipped the drift check,
    because the window is shut *today* — the demotion and the 0.3 confidence
    floor both silently vanished. No test in the repo passed now= to
    run_sleep, so the suite could not see it.
    """
    store = Store(str(tmp_path / "store"))
    store.init()
    m, src = _drifting(tmp_path)
    m["temporal"]["valid_from"] = "2026-05-01T00:00:00+00:00"
    m["temporal"]["valid_until"] = "2026-08-01T00:00:00+00:00"   # shut TODAY
    store.save([m])
    src.write_text("TIMEOUT = 90\n")                              # world moved on

    # Replayed at an instant INSIDE the window: must behave like a live memory.
    run_sleep(store, now="2026-06-01T00:00:00+00:00")
    got = store.load()[0]
    assert "drifted" in (got["flags"] or []), "replay used the wall clock, not the replayed instant"
    assert got["epistemic"]["confidence"] <= 0.3, "the drift confidence floor was skipped"


def test_replay_outside_the_window_still_holds(tmp_path):
    """The falsifier for the test above: same store, instant OUTSIDE the
    window, must NOT demote. Otherwise the fix would just be 'always check'."""
    store = Store(str(tmp_path / "store"))
    store.init()
    m, src = _drifting(tmp_path)
    m["temporal"]["valid_until"] = "2026-08-01T00:00:00+00:00"
    store.save([m])
    src.write_text("TIMEOUT = 90\n")
    run_sleep(store, now="2026-08-20T00:00:00+00:00")
    assert "drifted" not in (store.load()[0]["flags"] or [])


def test_expired_memory_is_not_left_permanently_overdue(tmp_path):
    """The `continue` that skipped scheduling froze review_due forever."""
    store = Store(str(tmp_path / "store"))
    store.init()
    m, _ = _drifting(tmp_path)
    m["temporal"]["valid_until"] = _iso(-1)
    m["epistemic"]["review_due"] = "2026-01-02T00:00:00+00:00"
    m["epistemic"]["last_reviewed"] = "2026-01-01T00:00:00+00:00"
    store.save([m])
    run_sleep(store)
    ep = store.load()[0]["epistemic"]
    assert ep["last_reviewed"] != "2026-01-01T00:00:00+00:00", "last_reviewed frozen"
    assert ep["review_due"] > "2026-01-02", "expired memory left permanently overdue"


def test_force_is_orthogonal_to_grade_and_scope(tmp_path):
    """in_force must never be smuggled into evidence_status."""
    m, _ = _drifting(tmp_path)
    m["temporal"]["valid_until"] = _iso(-1)
    status, _, _ = grade(m)
    assert status in ("unverified", "source_linked", "machine_checked")
    assert status != "historical", "valid time leaked into the grade vocabulary"
