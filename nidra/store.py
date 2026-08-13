"""nidra.store — the evidence-graded memory store.

One memory is one JSON object on one line of ``memories.jsonl``. Every mutation
appends an event to ``journal.jsonl`` — the store never destroys, it supersedes
and tombstones, so forgetting stays auditable.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

MEMORIES = "memories.jsonl"
JOURNAL = "journal.jsonl"

EVIDENCE_STATES = ("unverified", "source_linked", "machine_checked")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize(text: str) -> str:
    """Casefold + collapse everything non-alphanumeric — the dedup key."""
    text = unicodedata.normalize("NFC", text or "").lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def mem_id(statement: str) -> str:
    return "mem_" + sha256_text(normalize(statement))[:12]


def new_memory(
    statement: str,
    subject: Optional[str] = None,
    source: Optional[str] = None,
    excerpt: Optional[str] = None,
    locator: Optional[str] = None,
    tags: Optional[List[str]] = None,
    confidence: float = 0.5,
    now: Optional[str] = None,
) -> Dict[str, Any]:
    now = now or utcnow()
    evidence = []
    if source and excerpt:
        evidence.append(
            {
                "source": source,
                "excerpt": excerpt,
                "sha256": sha256_text(excerpt),
                "locator": locator,
                "checked_at": None,
            }
        )
    return {
        "id": mem_id(statement),
        "statement": statement,
        "subject": subject,
        "tags": tags or [],
        "epistemic": {
            "evidence_status": "unverified",
            "confidence": confidence,
            "last_reviewed": None,
            "review_due": now,
        },
        "evidence": evidence,
        "temporal": {"recorded_at": now, "superseded_by": None},
        "flags": [],
        "active": True,
    }


class Store:
    """A directory holding memories.jsonl + journal.jsonl."""

    def __init__(self, root: str):
        self.root = root
        self.memories_path = os.path.join(root, MEMORIES)
        self.journal_path = os.path.join(root, JOURNAL)

    def init(self) -> None:
        os.makedirs(self.root, exist_ok=True)
        for p in (self.memories_path, self.journal_path):
            if not os.path.exists(p):
                open(p, "w", encoding="utf-8").close()
        self.journal({"event": "init"})

    def exists(self) -> bool:
        return os.path.exists(self.memories_path)

    def load(self) -> List[Dict[str, Any]]:
        if not self.exists():
            return []
        with open(self.memories_path, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def save(self, mems: List[Dict[str, Any]]) -> None:
        tmp = self.memories_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            for m in mems:
                fh.write(json.dumps(m, ensure_ascii=False) + "\n")
        os.replace(tmp, self.memories_path)

    def journal(self, event: Dict[str, Any]) -> None:
        event = dict(event)
        event.setdefault("ts", utcnow())
        with open(self.journal_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")

    def journal_for(self, mid: str) -> List[Dict[str, Any]]:
        if not os.path.exists(self.journal_path):
            return []
        out = []
        with open(self.journal_path, encoding="utf-8") as fh:
            for line in fh:
                if mid in line:
                    out.append(json.loads(line))
        return out

    def add(self, mem: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a memory; if the id already exists, union its evidence."""
        mems = self.load()
        for existing in mems:
            if existing["id"] == mem["id"]:
                seen = {(e["source"], e["excerpt"]) for e in existing["evidence"]}
                for ev in mem["evidence"]:
                    if (ev["source"], ev["excerpt"]) not in seen:
                        existing["evidence"].append(ev)
                self.save(mems)
                self.journal({"event": "evidence_added", "id": mem["id"]})
                return existing
        mems.append(mem)
        self.save(mems)
        self.journal({"event": "added", "id": mem["id"], "statement": mem["statement"]})
        return mem

    def get(self, mid: str) -> Optional[Dict[str, Any]]:
        for m in self.load():
            if m["id"] == mid:
                return m
        return None
