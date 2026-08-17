# Field notes: what a production Sanskrit RAG taught Nidra

Nidra did not fall from theory. It generalizes lessons paid for, in production,
by [PuranGPT](https://purangpt.com) — a RAG system over the Sanskrit canon
(≈368K verse rows across ~45 texts, a 9K-entity / 25K-edge knowledge graph, a
typed teaching memory, live users). PuranGPT ran *several independent research
passes* on retrieval and memory over months; Nidra encodes what survived them.
This page maps the two architectures and the four lessons they proved twice —
once the slow way, once the designed way.

## The two systems, side by side

| | PuranGPT (production RAG) | Nidra (trust layer) |
|---|---|---|
| Job | answer seekers from scripture, with citations | grade any memory store's honesty |
| Fact layer | Postgres corpus rows; hybrid keyword + e5-large semantic lanes | *bring your own store* — Nidra sits beside it |
| Wisdom layer | knowledge graph + typed teaching memory (interpretation, never fact-source) | graded memories: evidence rows, hash-anchored |
| Judgment | deterministic precedence merge; the stochastic "Witness" relevance-cull was **removed** | five deterministic stages; LLM judge optional, last, fail-open |
| Provenance | citation guards keep non-citable content out of citations | attribution rides every edge; grades are earned, never asserted |

## Four lessons, proven twice

**1. Encoding variance must never masquerade as absence — or as drift.**
PuranGPT's keyword lane silently lost **85,267 Devanagari rows** (28% of its
corpus) to an ASCII-only assumption; the measured fix — emit both script forms,
"reach is only ever added" — took a query like `%कलियुग%` from 0 hits to 49.
Nidra hit the *same* wall from the other side: ASCII-only evidence anchors
first produced 114 false "drifts" (non-ASCII and rendering prefixes), then
locked 26% of a real archive out of receipts entirely. The imported cure:
anchors prefer ASCII, fall back to clean unicode, and the grader checks **both
the raw and the JSON-escaped form** before ever saying "drifted." Measured on
the archive's Devanagari-heavy wing: 2,709 previously unverifiable memories
recovered receipts (no-anchor rate 34.6% → 30.2%); the remainder is genuinely
short or fragment-heavy text, and stays honestly `unverified`.

**2. Deterministic first; judgment last, and fail-open.**
PuranGPT once ran an LLM "Witness" judge in its hot retrieval path — and
removed it, replacing it with deterministic, precedence-ordered organs and
dedup. Nidra was born with that ending: five deterministic sleep stages cost
zero tokens; only genuinely contested pairs may see a model, and an
unreachable judge leaves them flagged for a human, never guessed.

**3. Facts and interpretation never mix — and attribution rides the data.**
PuranGPT's hardest scar: an automatic decoder that fabricated real-looking
citations. The resulting doctrine — *facts from retrieval, wisdom from the
graph, the decoder is never a fact source*, with a triple guard keeping
non-citable content out of citations — is Nidra's schema: the statement is
interpretation; the **evidence row** (source + exact excerpt + sha256) is the
only fact claim; and grades (`unverified → source_linked → machine_checked`)
say exactly which is which, per memory, forever.

**4. Grade your own store before selling anyone else's honesty.**
PuranGPT audited itself and kept finding the same disease in new organs:
scraped webpage markup ingested as scripture, an archive.org text swapped
under a source id, a teaching memory only 4% source-linked. Each got an ad-hoc
tool. Nidra is that tool generalized — and dogfooded: its own birthplace
archive graded at **22.7% byte-traceable, 53.7% sources gone, 2,551 drift
candidates** across 474,779 memories. The audit that audits itself is the
product.

## What flows back

The bridge runs both ways. PuranGPT's next moves, now cheaper because Nidra
exists: the **re-grading daemon** for its 1,299 still-unverified teachings can
run through Nidra's key-free Claude Code judge; and its corpus-provenance
sweeps (the markup-row and swapped-source incidents) are one adapter away from
being scheduled sleep passes instead of hand-built one-offs.

Two systems, one law, learned at two scales: **no claim without a receipt,
and re-check the receipt, because the world moves.**
