"""nidra.recall — the answer cache that can prove it's still valid.

The oldest hard problem in caching is invalidation; the oldest hard problem in
AI memory is staleness. They are the same problem, and a trust-graded memory
solves both at once: **an answer cached with evidence receipts serves only
while the receipts still verify.**

- ``remember(...)`` stores a question+answer pair as a memory whose evidence
  rows are the *sources the answer actually used*.
- ``recall(...)`` looks the question up (exact normalized key, then lexical
  fuzzy match for similar phrasings) and **re-grades the entry at serve time**:
  if any source drifted since the answer was cached, the entry silently stops
  serving — no TTL guesswork, no stale confident answer. The sleep pass keeps
  doing the same on schedule, and conflicting cached answers to one question
  share a subject, so the contradiction stage can catch and supersede them.
- ``prewarm(...)`` runs a question list through any answerer (the Claude Code
  bridge, your RAG, anything) and remembers the results — the "finite question
  space" motion: if you know what people ask, answer it before they do, with
  receipts, and let the sleep pass keep the pre-cache honest.

Serving preference: the newest qualifying entry wins (an updated answer
outranks its predecessors even before a judge formally supersedes them).
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from .grade import grade
from .retrieval import retrieve
from .store import Store, new_memory, normalize, sha256_text

CACHE_TAG = "recall-cache"
_GRADE_RANK = {"unverified": 0, "source_linked": 1, "machine_checked": 2}

Source = Tuple[str, str, Optional[str]]  # (source_path, excerpt, locator)


def question_key(question: str) -> str:
    return normalize(question)


def remember(
    store: Store,
    question: str,
    answer: str,
    sources: Iterable[Source] = (),
    now: Optional[str] = None,
) -> Dict[str, Any]:
    """Cache an answer as a graded memory carrying its receipts."""
    key = question_key(question)
    statement = "Q: %s\nA: %s" % (question.strip(), answer.strip())
    sources = list(sources)
    first = sources[0] if sources else (None, None, None)
    mem = new_memory(
        statement,
        subject="recall:" + key,
        source=first[0],
        excerpt=first[1],
        locator=first[2],
        tags=[CACHE_TAG],
        now=now,
    )
    for src, excerpt, locator in sources[1:]:
        mem["evidence"].append(
            {
                "source": src,
                "excerpt": excerpt,
                "sha256": sha256_text(excerpt),
                "locator": locator,
                "checked_at": None,
            }
        )
    # distinct id per (question, answer): an updated answer coexists with its
    # predecessor as a separate row; same subject → the contradiction stage and
    # recency preference handle the succession.
    mem["id"] = "mem_" + sha256_text("recall|" + key + "|" + normalize(answer))[:12]
    return store.add(mem)


def _answer_of(mem: Dict[str, Any]) -> str:
    _, _, answer = mem["statement"].partition("\nA: ")
    return answer.strip()


def _question_of(mem: Dict[str, Any]) -> str:
    head = mem["statement"].split("\nA: ", 1)[0]
    return head[3:].strip() if head.startswith("Q: ") else head.strip()


def _qualifies(mem: Dict[str, Any], min_grade: str) -> Optional[str]:
    """Live serve-time check. Returns the current grade if servable, else None."""
    if not mem["active"] or "contested" in mem["flags"]:
        return None
    status, _, _ = grade(mem)  # re-verify receipts NOW — drift stops serving
    if _GRADE_RANK[status] < _GRADE_RANK[min_grade]:
        return None
    return status


def recall(
    store: Store,
    question: str,
    min_grade: str = "machine_checked",
    fuzzy: bool = True,
    k: int = 3,
) -> Optional[Dict[str, Any]]:
    """Serve a cached answer only if its receipts still verify."""
    key = question_key(question)
    entries = [m for m in store.load() if CACHE_TAG in m["tags"]]
    exact = [m for m in entries if m.get("subject") == "recall:" + key]
    candidates = sorted(exact, key=lambda m: m["temporal"]["recorded_at"], reverse=True)
    if not candidates and fuzzy and entries:
        shaped = [dict(m, statement=_question_of(m)) for m in entries]
        by_id = {m["id"]: m for m in entries}
        candidates = [by_id[s["id"]] for s in retrieve(shaped, question, k=k)]
        candidates.sort(key=lambda m: m["temporal"]["recorded_at"], reverse=True)
    for mem in candidates:
        current_grade = _qualifies(mem, min_grade)
        if current_grade is not None:
            return {
                "answer": _answer_of(mem),
                "question": _question_of(mem),
                "memory_id": mem["id"],
                "grade": current_grade,
                "exact": bool(exact),
            }
    return None


Answerer = Callable[[str], Tuple[str, List[Source]]]


def prewarm(
    store: Store,
    questions: Iterable[str],
    answerer: Answerer,
    min_grade: str = "machine_checked",
) -> Dict[str, int]:
    """Answer the known question space ahead of demand, with receipts."""
    stats = {"asked": 0, "already_cached": 0, "warmed": 0, "failed": 0}
    for question in questions:
        stats["asked"] += 1
        if recall(store, question, min_grade=min_grade, fuzzy=False) is not None:
            stats["already_cached"] += 1
            continue
        try:
            answer, sources = answerer(question)
        except Exception:
            stats["failed"] += 1
            continue
        remember(store, question, answer, sources)
        stats["warmed"] += 1
    return stats
