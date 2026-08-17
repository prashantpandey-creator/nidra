"""The recall cache: serves only what still verifies."""
from nidra.recall import prewarm, recall, remember
from nidra.sleep import run_sleep
from nidra.store import Store


def make_store(tmp_path):
    store = Store(str(tmp_path / "palace"))
    store.init()
    return store


def write_source(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_hit_serves_while_receipts_verify(tmp_path):
    store = make_store(tmp_path)
    src = write_source(tmp_path, "config.md", "the retry limit is 5 for all clients")
    remember(store, "What is the retry limit?", "It is 5.",
             [(src, "retry limit is 5", "config.md#L1")])
    hit = recall(store, "What is the retry limit?")
    assert hit is not None and hit["answer"] == "It is 5." and hit["grade"] == "machine_checked"
    assert hit["exact"] is True


def test_serve_time_invalidation_on_source_drift(tmp_path):
    """The whole thesis in one test: drift stops serving, before any sleep."""
    store = make_store(tmp_path)
    src = write_source(tmp_path, "config.md", "the retry limit is 5 for all clients")
    remember(store, "What is the retry limit?", "It is 5.",
             [(src, "retry limit is 5", None)])
    assert recall(store, "What is the retry limit?") is not None
    write_source(tmp_path, "config.md", "the retry limit is 6 for all clients")
    assert recall(store, "What is the retry limit?") is None          # invalidated live
    hit = recall(store, "What is the retry limit?", min_grade="unverified")
    assert hit is not None                                            # caller may opt down


def test_fuzzy_match_and_recency_preference(tmp_path):
    store = make_store(tmp_path)
    src = write_source(tmp_path, "notes.md", "the deploy runs on port 8000 behind nginx")
    remember(store, "Which port does the deploy use?", "Port 8000.",
             [(src, "runs on port 8000", None)], now="2026-01-01T00:00:00+00:00")
    fuzzy_hit = recall(store, "What port is the deploy running on?")
    assert fuzzy_hit is not None and fuzzy_hit["answer"] == "Port 8000." and not fuzzy_hit["exact"]

    remember(store, "Which port does the deploy use?", "Port 8000, behind nginx.",
             [(src, "port 8000 behind nginx", None)], now="2026-02-01T00:00:00+00:00")
    newest = recall(store, "Which port does the deploy use?")
    assert newest["answer"] == "Port 8000, behind nginx."             # newest wins


def test_sleep_keeps_the_cache_honest(tmp_path):
    store = make_store(tmp_path)
    src = write_source(tmp_path, "doc.md", "the bucket name is alpha for uploads")
    remember(store, "What is the bucket name?", "alpha", [(src, "bucket name is alpha", None)])
    run_sleep(store)
    write_source(tmp_path, "doc.md", "the bucket name is beta for uploads")
    run_sleep(store)  # scheduled pass demotes the drifted entry
    entry = [m for m in store.load() if "recall-cache" in m["tags"]][0]
    assert "drifted" in entry["flags"]
    assert recall(store, "What is the bucket name?") is None


def test_prewarm_answers_only_misses(tmp_path):
    store = make_store(tmp_path)
    src = write_source(tmp_path, "kb.md", "support hours are nine to five on weekdays")
    calls = []

    def answerer(question):
        calls.append(question)
        return "Nine to five, weekdays.", [(src, "support hours are nine to five", None)]

    stats = prewarm(store, ["What are the support hours?", "When is support open?"], answerer)
    assert stats == {"asked": 2, "already_cached": 0, "warmed": 2, "failed": 0}
    stats2 = prewarm(store, ["What are the support hours?", "When is support open?"], answerer)
    assert stats2["already_cached"] == 2 and stats2["warmed"] == 0
    assert len(calls) == 2                                            # never re-answered

    def broken(question):
        raise RuntimeError("no bridge")

    stats3 = prewarm(store, ["A brand new question nobody cached?"], broken)
    assert stats3["failed"] == 1                                      # fail-open, no fake entry
