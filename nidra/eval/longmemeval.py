"""nidra.eval.longmemeval — LongMemEval through the Nidra pipeline.

LongMemEval (Wu et al., ICLR 2025; huggingface.co/datasets/xiaowu0162/longmemeval)
poses 500 questions over long chat histories, with the evidence sessions
labeled per question. This harness runs the *real* Nidra pipeline per question:

    materialize sessions as a source file  →  ingest turns as memories with
    evidence anchors  →  run the sleep pass (dedup + grade against the source
    bytes)  →  retrieve top-k over active memories  →  score.

The reported metric is **evidence recall@k** — did the top-k retrieved
memories include at least one from a labeled answer session? It is keyless and
deterministic: no generation, no LLM judge, nothing to dispute. End-to-end QA
accuracy (answer generation + judging) requires model calls and is deliberately
NOT reported until run; the harness is public precisely so the number cannot
precede the machine that produces it.

Retrieval is a deliberately plain lexical scorer (tf-idf over the question's
own store). Nidra is not a retriever; the point is that the *pipeline* —
receipts, grading, consolidation — carries a standard benchmark unmodified.

Abstention variants (question_id ending ``_abs``) have no valid evidence and
are excluded from recall, counted separately.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import time
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

from ..adapters.mempalace import clean_anchor
from ..sleep import run_sleep
from ..store import Store, new_memory, normalize, sha256_text

STATEMENT_CAP = 800


def load_questions(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _flatten(content: str) -> str:
    return " ".join((content or "").split())


def ingest_question(q: Dict[str, Any], workdir: str) -> Store:
    """Materialize one question's haystack and ingest it as a Nidra store."""
    qdir = os.path.join(workdir, "q_" + q["question_id"])
    if os.path.exists(qdir):
        shutil.rmtree(qdir)
    os.makedirs(os.path.join(qdir, "sources"))
    source_path = os.path.join(qdir, "sources", "haystack.txt")

    lines: List[str] = []
    mems: List[Dict[str, Any]] = []
    for sid, session in zip(q["haystack_session_ids"], q["haystack_sessions"]):
        for turn_no, turn in enumerate(session):
            text = _flatten(turn.get("content", ""))
            if not text:
                continue
            lines.append(text)
            statement = "[%s] %s" % (turn.get("role", "?"), text[:STATEMENT_CAP])
            anchor = clean_anchor(text)
            mem = new_memory(
                statement,
                source=source_path if anchor else None,
                excerpt=anchor,
                locator="%s#turn%d" % (sid, turn_no),
                tags=["longmemeval", "session:%s" % sid],
            )
            # unique per (question, session, turn): identical filler turns in
            # different sessions must remain distinct rows for attribution
            mem["id"] = "mem_" + sha256_text(
                "|".join((q["question_id"], sid, str(turn_no), text))
            )[:12]
            mems.append(mem)

    with open(source_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    store = Store(os.path.join(qdir, "palace"))
    store.init()
    store.save(mems)
    return store


def retrieve(mems: List[Dict[str, Any]], query: str, k: int = 5) -> List[Dict[str, Any]]:
    """Plain lexical tf-idf over the question's own store."""
    docs = [(m, Counter(normalize(m["statement"]).split())) for m in mems if m["active"]]
    n_docs = len(docs) or 1
    df: Counter = Counter()
    for _, tokens in docs:
        df.update(tokens.keys())
    q_tokens = normalize(query).split()
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for m, tokens in docs:
        score = 0.0
        for t in q_tokens:
            if t in tokens:
                score += (1 + math.log(tokens[t])) * math.log(n_docs / (1 + df[t]) + 1)
        if score > 0:
            scored.append((score, m))
    scored.sort(key=lambda pair: -pair[0])
    return [m for _, m in scored[:k]]


def _sessions_of(mems: List[Dict[str, Any]]) -> List[str]:
    out = []
    for m in mems:
        for tag in m["tags"]:
            if tag.startswith("session:"):
                out.append(tag[len("session:"):])
    return out


def run(
    data_path: str,
    workdir: str,
    k: int = 5,
    limit: Optional[int] = None,
    keep_stores: bool = False,
) -> Dict[str, Any]:
    questions = load_questions(data_path)
    if limit:
        questions = questions[:limit]
    os.makedirs(workdir, exist_ok=True)

    per_type_hit: Dict[str, int] = defaultdict(int)
    per_type_n: Dict[str, int] = defaultdict(int)
    grades: Counter = Counter()
    abstention = 0
    t0 = time.time()

    for q in questions:
        if q["question_id"].endswith("_abs"):
            abstention += 1
            continue
        store = ingest_question(q, workdir)
        run_sleep(store)
        mems = store.load()
        for m in mems:
            if m["active"]:
                grades[m["epistemic"]["evidence_status"]] += 1
        top = retrieve(mems, q["question"], k=k)
        hit = bool(set(_sessions_of(top)) & set(q["answer_session_ids"]))
        qtype = q["question_type"]
        per_type_n[qtype] += 1
        per_type_hit[qtype] += int(hit)
        if not keep_stores:
            shutil.rmtree(os.path.join(workdir, "q_" + q["question_id"]), ignore_errors=True)

    scored = sum(per_type_n.values())
    hits = sum(per_type_hit.values())
    return {
        "dataset": os.path.basename(data_path),
        "k": k,
        "questions_scored": scored,
        "abstention_excluded": abstention,
        "recall_at_k": round(hits / scored, 4) if scored else None,
        "per_type": {
            t: {"n": per_type_n[t], "recall": round(per_type_hit[t] / per_type_n[t], 4)}
            for t in sorted(per_type_n)
        },
        "pipeline_grades": dict(grades),
        "seconds": round(time.time() - t0, 1),
    }
