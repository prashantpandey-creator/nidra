"""nidra.sleep — the consolidation pass ("the meditation").

Writing memories is cheap; an unconsolidated store only gets heavier. The
sleep pass is the half most memory systems skip, run in five deterministic
stages (an optional LLM judge is stage six, and only for genuinely contested
pairs):

1. **Dedup** — same normalized statement → merge into the oldest, union
   evidence, supersede the duplicates.
2. **Verify** — re-check every evidence row against its source bytes and
   re-grade. A verified memory whose source changed is *demoted*: a stale
   trust label is worse than none, because it is confident and wrong.
3. **Contradict** — same subject, negated or numerically conflicting
   statements → both flagged ``contested`` (a judge may resolve them).
4. **Schedule** — spaced-repetition review intervals: each clean re-check
   pushes the next review further out; any failure resets the clock.
5. **Prune** — evidence-free, low-confidence, long-overdue memories are
   tombstoned (never deleted; the journal keeps the record).

Every action is recorded; running the pass twice in an unchanged world
produces zero actions — consolidation is idempotent.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .grade import evidence_scope, grade
from .store import Store, normalize, utcnow

REVIEW_INTERVALS_DAYS = [1, 3, 7, 14, 30, 90]
PRUNE_CONFIDENCE = 0.4
PRUNE_OVERDUE_DAYS = 30

_NEG = re.compile(r"\b(not|never|no longer|isn t|is nt|dont|doesn t|does nt)\b")
_NUM = re.compile(r"\d+(?:\.\d+)?")


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    # Python <3.11 fromisoformat rejects the JS-style 'Z' suffix. The first
    # launchd heartbeat (system python 3.9.6) crashed the whole sleep pass on
    # one such timestamp; interactive runs (3.14) never saw it. One bad
    # timestamp must degrade to None, never kill consolidation.
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _denegate(norm: str) -> str:
    return re.sub(r"\s+", " ", _NEG.sub(" ", norm)).strip()


def _numbers(norm: str) -> List[str]:
    return _NUM.findall(norm)


def _template(norm: str) -> str:
    return _NUM.sub("#", norm)


def contradicts(statement_a: str, statement_b: str) -> Optional[str]:
    """Deterministic contradiction check. Returns a kind or None."""
    a, b = normalize(statement_a), normalize(statement_b)
    if a == b:
        return None
    if _denegate(a) == _denegate(b) and bool(_NEG.search(a)) != bool(_NEG.search(b)):
        return "negation"
    if _template(a) == _template(b) and _numbers(a) != _numbers(b):
        return "numeric"
    return None


def _flag(mem: Dict[str, Any], flag: str) -> bool:
    if flag not in mem["flags"]:
        mem["flags"].append(flag)
        return True
    return False


def _interval_index(days: float) -> int:
    for i, d in enumerate(REVIEW_INTERVALS_DAYS):
        if days <= d:
            return i
    return len(REVIEW_INTERVALS_DAYS) - 1


def run_sleep(store: Store, judge: Any = None, now: Optional[str] = None) -> Dict[str, Any]:
    now_iso = now or utcnow()
    now_dt = _parse_ts(now_iso)
    mems = store.load()
    report: Dict[str, Any] = {
        "started": now_iso,
        "before": census(mems),
        "actions": [],
        "contested": [],
    }

    def act(kind: str, mid: str, detail: str) -> None:
        report["actions"].append({"kind": kind, "id": mid, "detail": detail})
        store.journal({"event": "sleep." + kind, "id": mid, "detail": detail})

    # ---- stage 1: dedup ---------------------------------------------------
    by_key: Dict[str, Dict[str, Any]] = {}
    for m in mems:
        if not m["active"]:
            continue
        key = normalize(m["statement"])
        keeper = by_key.get(key)
        if keeper is None:
            by_key[key] = m
            continue
        if m["temporal"]["recorded_at"] < keeper["temporal"]["recorded_at"]:
            keeper, m = m, keeper
            by_key[key] = keeper
        seen = {(e["source"], e["excerpt"]) for e in keeper["evidence"]}
        for ev in m["evidence"]:
            if (ev["source"], ev["excerpt"]) not in seen:
                keeper["evidence"].append(ev)
        m["active"] = False
        m["temporal"]["superseded_by"] = keeper["id"]
        act("merged", m["id"], "duplicate of %s" % keeper["id"])

    # ---- stage 2: verify + re-grade --------------------------------------
    for m in mems:
        if not m["active"]:
            continue
        old_status = m["epistemic"]["evidence_status"]
        new_status, states, reasons = grade(m)
        if "corrupt" in states and _flag(m, "integrity"):
            act("integrity", m["id"], "; ".join(reasons))
        if "drifted" in states:
            if _flag(m, "drifted"):
                act("demoted", m["id"], "evidence drift: " + "; ".join(reasons))
            m["epistemic"]["confidence"] = min(m["epistemic"]["confidence"], 0.3)
        elif m["flags"] and "drifted" in m["flags"] and new_status == "machine_checked":
            m["flags"].remove("drifted")  # the world matches the memory again
        if new_status != old_status and "drifted" not in states:
            act(
                "regraded",
                m["id"],
                "%s -> %s (%s)" % (old_status, new_status, "; ".join(reasons)),
            )
        m["epistemic"]["evidence_status"] = new_status
        # Orthogonal to the grade: checked how well vs checked against
        # WHAT. 43% of evidenced memories were green on quote-only
        # evidence, which no change in the world can falsify.
        m["epistemic"]["evidence_scope"] = evidence_scope(m)
        if new_status == "machine_checked":
            m["epistemic"]["confidence"] = max(m["epistemic"]["confidence"], 0.9)
            for ev in m["evidence"]:
                ev["checked_at"] = now_iso
        elif new_status == "source_linked":
            m["epistemic"]["confidence"] = min(max(m["epistemic"]["confidence"], 0.6), 0.7)

        # ---- stage 4 (per-memory): review scheduling ---------------------
        last = _parse_ts(m["epistemic"].get("last_reviewed"))
        due = _parse_ts(m["epistemic"].get("review_due")) or now_dt
        prev_days = (due - last).days if last else 0
        if new_status == "machine_checked":
            idx = min(_interval_index(max(prev_days, 1)) + 1, len(REVIEW_INTERVALS_DAYS) - 1)
        else:
            idx = 0
        m["epistemic"]["last_reviewed"] = now_iso
        m["epistemic"]["review_due"] = (
            now_dt + timedelta(days=REVIEW_INTERVALS_DAYS[idx])
        ).isoformat()

    # ---- stage 3: contradictions -----------------------------------------
    by_subject: Dict[str, List[Dict[str, Any]]] = {}
    for m in mems:
        if m["active"] and m.get("subject"):
            by_subject.setdefault(m["subject"], []).append(m)
    for subject, group in by_subject.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                kind = contradicts(a["statement"], b["statement"])
                if not kind:
                    continue
                fresh = _flag(a, "contested") | _flag(b, "contested")
                pair = {
                    "subject": subject,
                    "kind": kind,
                    "a": {"id": a["id"], "statement": a["statement"]},
                    "b": {"id": b["id"], "statement": b["statement"]},
                }
                report["contested"].append(pair)
                if fresh:
                    act("contested", a["id"] + "+" + b["id"], "%s conflict on %r" % (kind, subject))
                if judge is not None:
                    verdict = judge.resolve(a, b) or {}
                    winner = verdict.get("winner")
                    if winner in ("a", "b"):
                        w, l = (a, b) if winner == "a" else (b, a)
                        l["active"] = False
                        l["temporal"]["superseded_by"] = w["id"]
                        _flag(l, "superseded_by_judgment")
                        act(
                            "judged",
                            l["id"],
                            "superseded by %s: %s" % (w["id"], verdict.get("reason", "")),
                        )

    # ---- stage 5: prune ---------------------------------------------------
    for m in mems:
        if not m["active"] or m["evidence"]:
            continue
        due = _parse_ts(m["epistemic"].get("review_due"))
        recorded = _parse_ts(m["temporal"]["recorded_at"])
        overdue_from = min(d for d in (due, recorded) if d is not None)
        overdue_days = (now_dt - overdue_from).days
        if (
            m["epistemic"]["confidence"] <= PRUNE_CONFIDENCE
            and overdue_days > PRUNE_OVERDUE_DAYS
            and "contested" not in m["flags"]
        ):
            m["active"] = False
            _flag(m, "tombstoned")
            act("tombstoned", m["id"], "unverified, low-confidence, %sd overdue" % overdue_days)

    report["after"] = census(mems)
    store.save(mems)
    store.journal(
        {
            "event": "sleep.completed",
            "actions": len(report["actions"]),
            "contested": len(report["contested"]),
        }
    )
    return report


def census(mems: List[Dict[str, Any]]) -> Dict[str, Any]:
    out = {"total": len(mems), "active": 0, "by_status": {}, "contested": 0}
    for m in mems:
        if not m["active"]:
            continue
        out["active"] += 1
        status = m["epistemic"]["evidence_status"]
        out["by_status"][status] = out["by_status"].get(status, 0) + 1
        if "contested" in m["flags"]:
            out["contested"] += 1
    return out
