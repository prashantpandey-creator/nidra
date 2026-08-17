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


# ---- QA stage: answers + judging through Claude Code (no API key) ---------

_TAG_LINE = None  # compiled lazily per tag


def _pack_answer_prompt(items: List[Tuple[int, str, List[str]]]) -> str:
    parts = [
        "You answer questions strictly from the memory snippets provided with each item.",
        "For each item output exactly one line, nothing else: 'A<n>: <short answer>'.",
        "If the snippets do not contain the answer, output exactly 'A<n>: No information available'.",
        "",
    ]
    for idx, question, contexts in items:
        parts.append("### Item %d" % idx)
        for c in contexts:
            parts.append("- %s" % c)
        parts.append("Question %d: %s" % (idx, question))
        parts.append("")
    return "\n".join(parts)


def _pack_judge_prompt(items: List[Tuple[int, str, str, str]]) -> str:
    parts = [
        "Grade each hypothesis against its gold answer for the given question.",
        "Paraphrase counts as correct. When the gold answer indicates the information",
        "is unavailable or unknown, the hypothesis is correct only if it also declines.",
        "For each item output exactly one line: 'J<n>: CORRECT' or 'J<n>: WRONG'.",
        "",
    ]
    for idx, question, gold, hyp in items:
        parts.append("### Item %d" % idx)
        parts.append("Question: %s" % question)
        parts.append("Gold: %s" % gold)
        parts.append("Hypothesis: %s" % hyp)
        parts.append("")
    return "\n".join(parts)


def _parse_tagged(text: str, tag: str) -> Dict[int, str]:
    import re as _re

    out: Dict[int, str] = {}
    for m in _re.finditer(r"(?m)^\s*%s(\d+)\s*:\s*(.+?)\s*$" % tag, text or ""):
        out[int(m.group(1))] = m.group(2)
    return out


def run_qa(
    data_path: str,
    workdir: str,
    k: int = 5,
    limit: Optional[int] = None,
    model: Optional[str] = "haiku",
    batch: int = 6,
    workers: int = 4,
    ask=None,
) -> Dict[str, Any]:
    """End-to-end QA accuracy: retrieve -> answer -> judge, via Claude Code."""
    from concurrent.futures import ThreadPoolExecutor

    if ask is None:
        from ..claude_cli import ask_claude as ask

    questions = load_questions(data_path)
    if limit:
        questions = questions[:limit]
    os.makedirs(workdir, exist_ok=True)
    t0 = time.time()

    rows: List[Dict[str, Any]] = []
    for i, q in enumerate(questions):
        store = ingest_question(q, workdir)
        run_sleep(store)
        top = retrieve(store.load(), q["question"], k=k)
        rows.append(
            {
                "idx": i,
                "q": q,
                "contexts": [m["statement"][:400] for m in top],
            }
        )
        shutil.rmtree(os.path.join(workdir, "q_" + q["question_id"]), ignore_errors=True)

    def _chunks(seq: List[Any]) -> List[List[Any]]:
        return [seq[i : i + batch] for i in range(0, len(seq), batch)]

    hyps: Dict[int, str] = {}
    unparsed = 0

    def _answer(chunk: List[Dict[str, Any]]) -> Dict[int, str]:
        prompt = _pack_answer_prompt(
            [(r["idx"], r["q"]["question"], r["contexts"]) for r in chunk]
        )
        try:
            return _parse_tagged(ask(prompt, model=model), "A")
        except Exception:
            return {}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for parsed in pool.map(_answer, _chunks(rows)):
            hyps.update(parsed)

    verdicts: Dict[int, str] = {}

    def _judge(chunk: List[Dict[str, Any]]) -> Dict[int, str]:
        prompt = _pack_judge_prompt(
            [
                (
                    r["idx"],
                    r["q"]["question"],
                    r["q"]["answer"],
                    hyps.get(r["idx"], "No answer produced"),
                )
                for r in chunk
            ]
        )
        try:
            return _parse_tagged(ask(prompt, model=model), "J")
        except Exception:
            return {}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for parsed in pool.map(_judge, _chunks(rows)):
            verdicts.update(parsed)

    per_type_hit: Dict[str, int] = defaultdict(int)
    per_type_n: Dict[str, int] = defaultdict(int)
    abs_hit = abs_n = 0
    for r in rows:
        idx, q = r["idx"], r["q"]
        verdict = verdicts.get(idx)
        if verdict is None or idx not in hyps:
            unparsed += 1
        correct = verdict is not None and verdict.strip().upper().startswith("CORRECT")
        if q["question_id"].endswith("_abs"):
            abs_n += 1
            abs_hit += int(correct)
        qtype = q["question_type"]
        per_type_n[qtype] += 1
        per_type_hit[qtype] += int(correct)

    scored = sum(per_type_n.values())
    hits = sum(per_type_hit.values())
    return {
        "dataset": os.path.basename(data_path),
        "stage": "qa",
        "bridge": "claude-code-cli",
        "model": model,
        "k": k,
        "questions_scored": scored,
        "accuracy": round(hits / scored, 4) if scored else None,
        "per_type": {
            t: {"n": per_type_n[t], "accuracy": round(per_type_hit[t] / per_type_n[t], 4)}
            for t in sorted(per_type_n)
        },
        "abstention": {"n": abs_n, "accuracy": round(abs_hit / abs_n, 4) if abs_n else None},
        "unparsed": unparsed,
        "seconds": round(time.time() - t0, 1),
    }
