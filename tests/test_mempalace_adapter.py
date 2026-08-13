"""Adapter tests against a miniature palace built to Chroma's real shape."""
import json
import sqlite3

from nidra.adapters.mempalace import clean_anchor, import_palace, iter_drawers
from nidra.sleep import run_sleep
from nidra.store import Store

DRAWERS_COLL = "coll-drawers"
CLOSETS_COLL = "coll-closets"


def build_fake_palace(root, drawers):
    """root/palace/chroma.sqlite3 with the tables the adapter reads."""
    palace_dir = root / "palace"
    palace_dir.mkdir(parents=True)
    db = sqlite3.connect(str(palace_dir / "chroma.sqlite3"))
    cur = db.cursor()
    cur.execute("CREATE TABLE collections (id TEXT, name TEXT)")
    cur.execute("CREATE TABLE segments (id TEXT, scope TEXT, collection TEXT)")
    cur.execute(
        "CREATE TABLE embeddings (id INTEGER PRIMARY KEY, segment_id TEXT, embedding_id TEXT)"
    )
    cur.execute(
        "CREATE TABLE embedding_metadata "
        "(id INTEGER, key TEXT, string_value TEXT, int_value INTEGER, float_value REAL)"
    )
    cur.execute("INSERT INTO collections VALUES (?, 'mempalace_drawers')", (DRAWERS_COLL,))
    cur.execute("INSERT INTO collections VALUES (?, 'mempalace_closets')", (CLOSETS_COLL,))
    cur.execute("INSERT INTO segments VALUES ('seg-meta', 'METADATA', ?)", (DRAWERS_COLL,))
    cur.execute("INSERT INTO segments VALUES ('seg-vec', 'VECTOR', ?)", (DRAWERS_COLL,))
    cur.execute("INSERT INTO segments VALUES ('seg-closet', 'METADATA', ?)", (CLOSETS_COLL,))
    for i, d in enumerate(drawers, start=1):
        cur.execute(
            "INSERT INTO embeddings VALUES (?, ?, ?)",
            (i, d.pop("_segment", "seg-meta"), d.pop("_id", "drawer_%d" % i)),
        )
        for key, value in d.items():
            cur.execute(
                "INSERT INTO embedding_metadata (id, key, string_value) VALUES (?, ?, ?)",
                (i, key, str(value)),
            )
    db.commit()
    db.close()
    return str(root)


def test_clean_anchor_survives_json_escaping():
    text = 'He said "hello"\nthen the retry limit was decided to be five for all clients'
    anchor = clean_anchor(text)
    assert anchor is not None
    assert '"' not in anchor and "\n" not in anchor and "\\" not in anchor
    assert anchor in json.dumps(text)  # the anchor survives JSON encoding verbatim
    assert clean_anchor('a "b" c\nd') is None  # nothing long enough


def test_clean_anchor_is_ascii_and_prefix_free():
    text = "> The naïve résumé is here and this line is long enough for anchoring"
    anchor = clean_anchor(text)
    assert anchor is not None
    assert anchor.isascii()                      # immune to ensure_ascii variance
    assert not anchor.startswith(">")            # rendering prefix is not source bytes
    # an escaping writer emits the anchor verbatim either way:
    assert anchor in json.dumps(text, ensure_ascii=True)
    assert anchor in json.dumps(text, ensure_ascii=False)


def test_import_and_sleep_grades_the_palace(tmp_path):
    good_src = tmp_path / "session.jsonl"
    good_text = "the team decided the retry limit should be five for all outbound clients"
    good_src.write_text(json.dumps({"type": "message", "text": good_text}) + "\n")

    palace = build_fake_palace(
        tmp_path / "mp",
        [
            {  # verifiable drawer
                "chroma:document": good_text,
                "source_file": str(good_src),
                "wing": "sessions",
                "room": "decisions",
                "filed_at": "2026-08-01T00:00:00",
            },
            {  # source vanished
                "chroma:document": "an architectural note whose transcript is long gone away",
                "source_file": str(tmp_path / "gone.jsonl"),
                "wing": "sessions",
                "room": "architecture",
            },
            {  # no clean anchor: quotes everywhere
                "chroma:document": '"a" "b" "c" "d" "e" "f" "g" "h" "i" "j" "k" "l" "m"',
                "source_file": str(good_src),
                "wing": "sessions",
                "room": "general",
            },
            {  # closet row: must be ignored
                "chroma:document": "closet content that must not be imported",
                "_segment": "seg-closet",
            },
        ],
    )

    assert len(list(iter_drawers(palace))) == 3  # closet excluded

    store = Store(str(tmp_path / "store"))
    store.init()
    summary = import_palace(store, palace=palace)
    assert summary["imported"] == 3
    assert summary["no_anchor"] == 1
    assert summary["rooms"] == {"decisions": 1, "architecture": 1, "general": 1}

    report = run_sleep(store)
    statuses = sorted(
        m["epistemic"]["evidence_status"] for m in store.load() if m["active"]
    )
    assert statuses == ["machine_checked", "source_linked", "unverified"]

    # re-import is a no-op; a following sleep takes no actions
    again = import_palace(store, palace=palace)
    assert again["imported"] == 0 and again["merged_existing"] == 3
    assert run_sleep(store)["actions"] == []


def test_room_filter_and_limit(tmp_path):
    palace = build_fake_palace(
        tmp_path / "mp",
        [
            {"chroma:document": "decision one about the deployment cadence of services",
             "room": "decisions", "wing": "w"},
            {"chroma:document": "decision two about the database backup retention window",
             "room": "decisions", "wing": "w"},
            {"chroma:document": "a general note that should not appear in this import",
             "room": "general", "wing": "w"},
        ],
    )
    rooms = [d["room"] for d in iter_drawers(palace, room="decisions")]
    assert rooms == ["decisions", "decisions"]
    assert len(list(iter_drawers(palace, limit=1))) == 1
