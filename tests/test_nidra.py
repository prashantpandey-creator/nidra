"""Nidra test battery — every claim in the README has an assertion here."""
import os

from nidra.cli import run_demo
from nidra.grade import grade, verify_evidence_row
from nidra.report import render_markdown
from nidra.sleep import contradicts, run_sleep
from nidra.store import Store, new_memory, normalize, sha256_text


def make_store(tmp_path):
    store = Store(str(tmp_path / "palace"))
    store.init()
    return store


# ---- store ----------------------------------------------------------------

def test_store_roundtrip_and_evidence_union(tmp_path):
    store = make_store(tmp_path)
    m = new_memory("The sky is blue", source="x.md", excerpt="sky is blue")
    store.add(m)
    dup = new_memory("The sky is blue", source="y.md", excerpt="blue sky again")
    store.add(dup)
    mems = store.load()
    assert len(mems) == 1
    assert len(mems[0]["evidence"]) == 2
    assert store.journal_for(m["id"])


def test_normalize_collapses_case_and_punctuation():
    assert normalize("Redis cache TTL is SEVEN days!!") == normalize("redis cache ttl is seven days")


# ---- grade ----------------------------------------------------------------

def test_grade_machine_checked_when_excerpt_in_source(tmp_path):
    src = tmp_path / "doc.md"
    src.write_text("the retry limit is 5 today")
    m = new_memory("retry limit is 5", source=str(src), excerpt="retry limit is 5")
    status, states, _ = grade(m)
    assert status == "machine_checked" and states == ["ok"]


def test_grade_drift_demotes_to_unverified(tmp_path):
    src = tmp_path / "doc.md"
    src.write_text("the retry limit is 5 today")
    m = new_memory("retry limit is 5", source=str(src), excerpt="retry limit is 5")
    src.write_text("the retry limit is 6 today")
    status, states, _ = grade(m)
    assert status == "unverified" and states == ["drifted"]


def test_grade_missing_source_is_source_linked(tmp_path):
    m = new_memory("x", source=str(tmp_path / "gone.md"), excerpt="anything")
    status, states, _ = grade(m)
    assert status == "source_linked" and states == ["source_missing"]


def test_grade_detects_store_tampering():
    m = new_memory("x", source="s.md", excerpt="original excerpt")
    m["evidence"][0]["excerpt"] = "tampered excerpt"  # sha no longer matches
    status, states, _ = grade(m)
    assert status == "unverified" and states == ["corrupt"]


def test_no_evidence_is_unverified():
    status, _, reasons = grade(new_memory("no receipts"))
    assert status == "unverified" and reasons == ["no evidence rows"]


# ---- contradictions -------------------------------------------------------

def test_contradicts_numeric_and_negation():
    assert contradicts("The timeout is 30 seconds", "The timeout is 60 seconds") == "numeric"
    assert contradicts("Telemetry is enabled", "Telemetry is not enabled") == "negation"
    assert contradicts("The timeout is 30 seconds", "The timeout is 30 seconds") is None
    assert contradicts("Cats purr", "Dogs bark") is None


# ---- sleep ----------------------------------------------------------------

def test_sleep_merges_promotes_and_is_idempotent(tmp_path):
    src = tmp_path / "doc.md"
    src.write_text("service listens on port 8000")
    store = make_store(tmp_path)
    store.add(new_memory("Service listens on port 8000", source=str(src), excerpt="listens on port 8000"))
    imported = new_memory("service listens on PORT 8000!")
    imported["id"] = "mem_foreign_id"  # a duplicate arriving from another store
    store.add(imported)
    report = run_sleep(store)
    kinds = [a["kind"] for a in report["actions"]]
    assert "merged" in kinds
    active = [m for m in store.load() if m["active"]]
    assert len(active) == 1
    assert active[0]["epistemic"]["evidence_status"] == "machine_checked"
    assert run_sleep(store)["actions"] == []


def test_sleep_judge_supersedes_loser(tmp_path):
    store = make_store(tmp_path)
    a = new_memory("The port is 80", subject="port")
    b = new_memory("The port is 8080", subject="port")
    store.add(a)
    store.add(b)

    class FakeJudge:
        def resolve(self, x, y):
            return {"winner": "b", "reason": "b is newer"}

    report = run_sleep(store, judge=FakeJudge())
    assert any(act["kind"] == "judged" for act in report["actions"])
    loser = store.get(a["id"]) if store.get(a["id"])["active"] is False else store.get(b["id"])
    assert loser["temporal"]["superseded_by"] is not None
    assert "superseded_by_judgment" in loser["flags"]


def test_report_renders_markdown(tmp_path):
    store = make_store(tmp_path)
    store.add(new_memory("solo fact"))
    md = render_markdown(run_sleep(store))
    assert "# Nidra trust report" in md and "unverified" in md


# ---- the whole proof ------------------------------------------------------

def test_demo_catches_every_planted_defect(tmp_path, monkeypatch):
    """The leak check must judge THIS run, not the repo's ambient state.

    It read ``.nidra-demo`` relative to whatever cwd pytest happened to have.
    Anyone running ``nidra demo`` by hand in the checkout left that directory
    behind (it is gitignored, so nothing complained), and every later run of
    the suite went red on residue it did not create. Measured 2026-08-25: red
    on a clean tree at HEAD, green the moment the stale directory was removed.
    A flake in the test that gates the release is worse than no gate — it
    trains you to ignore the one red light that matters.
    """
    monkeypatch.chdir(tmp_path)               # own the cwd, so a leak is ours
    rc = run_demo(str(tmp_path / "demo"), strict=True, quiet=True)
    assert rc == 0, "a planted defect went uncaught"
    assert not os.path.exists(".nidra-demo")  # demo stays inside tmp_path
