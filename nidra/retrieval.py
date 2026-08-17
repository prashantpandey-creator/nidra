"""nidra.retrieval — the plain lexical scorer shared by eval and recall.

Deliberately simple tf-idf; Nidra is not a retriever. Swap in an embedding
scorer if your domain needs paraphrase — the interfaces take any callable.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Any, Dict, List, Tuple

from .store import normalize


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
