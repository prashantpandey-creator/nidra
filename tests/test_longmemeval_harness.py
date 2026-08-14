"""The LongMemEval harness must run keyless, deterministically, honestly."""
import os

from nidra.eval.longmemeval import ingest_question, load_questions, retrieve, run
from nidra.sleep import run_sleep

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "longmemeval_mini.json")


def test_mini_end_to_end(tmp_path):
    result = run(FIXTURE, str(tmp_path / "work"), k=5)
    # 5 questions: 1 abstention excluded, 4 scored; mini_4 is a designed miss
    assert result["questions_scored"] == 4
    assert result["abstention_excluded"] == 1
    assert result["recall_at_k"] == 0.75
    assert result["per_type"]["temporal-reasoning"]["recall"] == 0.0  # the honest miss
    assert result["per_type"]["single-session-user"]["recall"] == 1.0
    assert result["per_type"]["multi-session"]["recall"] == 1.0
    assert result["per_type"]["knowledge-update"]["recall"] == 1.0
    # the pipeline is real: every ingested turn earned machine_checked receipts
    grades = result["pipeline_grades"]
    assert grades.get("machine_checked", 0) > 0
    assert grades.get("unverified", 0) == 0


def test_ingest_produces_verifiable_receipts(tmp_path):
    q = load_questions(FIXTURE)[0]
    store = ingest_question(q, str(tmp_path))
    run_sleep(store)
    active = [m for m in store.load() if m["active"]]
    assert all(m["epistemic"]["evidence_status"] == "machine_checked" for m in active)
    sessions = {t for m in active for t in m["tags"] if t.startswith("session:")}
    assert sessions == {"session:s1a", "session:s1b", "session:s1c"}


def test_retrieve_prefers_token_overlap(tmp_path):
    q = load_questions(FIXTURE)[0]
    store = ingest_question(q, str(tmp_path))
    top = retrieve(store.load(), q["question"], k=1)
    assert top and "session:s1a" in top[0]["tags"]
