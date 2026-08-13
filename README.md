# Nidra — the sleep cycle for AI memory

> **Every memory carries its evidence. A scheduled pass keeps the evidence honest.**

[![CI](https://github.com/prashantpandey-creator/nidra/actions/workflows/ci.yml/badge.svg)](https://github.com/prashantpandey-creator/nidra/actions/workflows/ci.yml)

*Nidrā* (निद्रा, Sanskrit: sleep) is the missing half of AI memory. Memory tools are
excellent at **writing** — mem0 layers it, Zep graphs it, Letta manages it, MemPalace
archives every word. But writing is the cheap half. Ask the harder questions:

- **Why should I believe this memory?** The [2026 surveys](https://www.graphlit.com/blog/survey-of-ai-agent-memory-frameworks)
  find no shipping system that grades trust; the academic critique is blunt — today's
  leaders ["treat all memories as equally trustworthy"](https://arxiv.org/pdf/2603.25097).
- **Is it still true?** A memory verified in June can be false by August. Nobody
  re-checks. A stale trust label is worse than none — it is confident and wrong.
- **Who keeps the store honest?** Unconsolidated stores only get heavier:
  duplicates, contradictions, dead weight — half a million entries and zero effect.

Nidra answers all three with one loop:

```
write → grade with evidence → sleep on schedule → recall by trust
```

## The 30-second proof

No API key, no setup, no trust required:

```bash
pip install git+https://github.com/prashantpandey-creator/nidra
nidra demo --strict
```

The demo plants a store with **known defects** — duplicates, contradictions,
stale junk, and a verified memory whose source file then changes — runs two
sleep passes, and verifies every defect was caught:

```
Planted 9 memories with 5 known defects. Night one:
| grade           | before | after |
| machine_checked |      0 |     2 |
| unverified      |      9 |     5 |
| contested       |      0 |     4 |

The world changed (retry limit 5 -> 6 in the source). Night two:
| machine_checked |      2 |     1 |   <- the stale badge, revoked

Proof:
  [PASS] duplicate pair merged
  [PASS] good memory promoted to machine_checked
  [PASS] numeric + negation contradictions flagged
  [PASS] overdue junk tombstoned
  [PASS] stale verified memory demoted after source change
  [PASS] third pass is a no-op (idempotent)
All planted defects caught. The pass proves itself.
```

CI runs exactly this on every commit — the badge above **is** the ongoing proof.
And every individual memory can be audited by hand:

```bash
nidra why mem_a1b2c3d4e5f6   # the memory, its excerpts, their hashes,
                             # and a live re-check against the source bytes
```

## First dogfood: grading a real palace

Nidra ships a **MemPalace adapter** ([MemPalace](https://github.com/MemPalace/mempalace)
mines conversations into a ChromaDB "palace"). The adapter reads the palace
strictly read-only and turns drawers into graded memories whose evidence points
back at the original transcript bytes:

```bash
nidra import-mempalace --room decisions --dir palace-audit
nidra sleep --dir palace-audit --report trust-report.md
```

We ran it on the 557,000-drawer palace Nidra was born next to — the
`decisions` and `problems` rooms, 4,063 drawers, graded in **0.4 seconds**:

| finding | count | share |
|---|---:|---:|
| still traceable to source bytes (`machine_checked`) | 482 | 12.6% |
| source transcript no longer exists (`source_linked`) | 3,266 | 85.5% |
| source exists but no longer contains the text (`drifted`) | 21 | 0.5% |
| no escaping-proof anchor (`unverified`, honest) | 52 | 1.4% |

Read that middle row again: **85% of this archive's receipts point at files
that are gone.** The memories may well be true — but nothing can re-verify
them anymore, and before this pass, nothing knew. Memory rot is real,
measurable, and silent; Nidra is the instrument that measures it.

One methodological note we're proud of: our first run reported 114 drifted
memories. A hand spot-check showed most were *our own artifact* — anchors
polluted by the palace's rendering prefixes and non-ASCII escaping variance —
so the anchor rules got stricter (pure printable ASCII, prefixes stripped),
false drift collapsed to 21 genuine cases, and the spot-check is now a test.
The audit must survive auditing itself.

## The grades

A memory's `evidence_status` is earned, never asserted:

| Grade | Meaning |
|---|---|
| `unverified` | No receipts, or receipts that failed re-checking. The honest default. |
| `source_linked` | Evidence recorded (source + exact excerpt + sha256) but not re-checkable right now. |
| `machine_checked` | At least one excerpt **re-verified against the source bytes** this pass, none drifted. |

Two independent checks guard each evidence row: **integrity** (does the stored
excerpt still match its own sha256 — detects store tampering) and **reality**
(does the source still contain the excerpt — detects the world changing).
Failure of the second *demotes* the memory, however confident it used to be.

## The sleep pass

Five deterministic stages — zero tokens, zero API keys — plus one optional LLM stage:

1. **Dedup** — normalized-equal statements merge; imported duplicates superseded, evidence unioned.
2. **Verify** — every evidence row re-checked against source bytes; grades recomputed; drift demotes.
3. **Contradict** — same subject, negated or numerically conflicting claims → both flagged `contested`.
4. **Schedule** — spaced-repetition review: clean checks push the next review out (1→3→7→14→30→90 days); any failure resets the clock.
5. **Prune** — evidence-free, low-confidence, long-overdue memories are **tombstoned, never deleted**: the journal keeps every byte, so forgetting stays auditable.
6. **Judge** *(optional)* — contested pairs go to a pluggable LLM judge
   (`nidra sleep --judge`, defaults to `claude-haiku-4-5`; fails open — an
   unreachable judge leaves the pair flagged for a human, never guessed).

Running the pass twice in an unchanged world produces **zero actions**.
Consolidation is idempotent; the report is a diff you can trust.

## Quickstart

```bash
nidra init
nidra add "The service listens on port 8000" \
    --subject service-port \
    --source docs/deploy.md --excerpt "listens on port 8000"
nidra sleep --report trust-report.md      # nightly, from cron
```

Or from Python:

```python
from nidra import Store, new_memory, run_sleep, render_markdown

store = Store(".nidra"); store.init()
store.add(new_memory("The retry limit is 5", subject="retry-limit",
                     source="config.md", excerpt="retry limit is 5"))
print(render_markdown(run_sleep(store)))
```

## Token economics

Nidra is deterministic-first by design: the entire pass costs nothing until a
pair is genuinely contested. When you do enable the judge, arbitration is a bulk
classification task — at Haiku pricing ($1/$5 per MTok) with the Batch API's 50%
discount, re-judging a **thousand** contested pairs costs on the order of **one
dollar**. The expensive part of memory was never the compute. It was that nobody
scheduled the sleep.

## Why not just use …

| | mem0 | Zep/Graphiti | Letta | MemPalace | **Nidra** |
|---|---|---|---|---|---|
| Recall / storage | ✅ | ✅ | ✅ | ✅ | ➖ *(bring your own)* |
| Temporal validity | ➖ | ✅ | ➖ | ➖ | ✅ supersede + journal |
| Sleep-time consolidation | ➖ | ➖ | ✅ | partial | ✅ five deterministic stages |
| **Evidence-graded trust** | ❌ | provenance only | ❌ | ❌ | ✅ hash-anchored grades |
| **Re-verification against sources** | ❌ | ❌ | ❌ | ❌ | ✅ every pass |
| **Auditable forgetting** | ❌ | ❌ | ❌ | ❌ | ✅ tombstones + journal |
| Works offline, zero keys | ❌ | ❌ | ❌ | ✅ | ✅ |

Nidra is deliberately **not** another store. It is the trust-and-consolidation
layer that mounts *beside* whichever store you already run. Storage is a solved
problem; honesty is not.

## Design principles

- **Deterministic first.** Anything a script can decide, a script decides. The
  LLM is reserved for judgment, and even then it is optional and fails open.
- **Single writer.** Parallel workers read and return verdicts; exactly one
  process writes the store. (Learned the hard way, in production.)
- **Never delete.** Supersede, tombstone, journal. A memory system that can
  silently destroy is a memory system you cannot audit.
- **Idempotent.** Same world in, zero actions out. Every action attributable.

## Roadmap

- ~~MemPalace adapter~~ — **shipped** (`nidra import-mempalace`; see the
  dogfood section above).
- **mem0 / file-store adapters.**
- **Published eval harness** — LongMemEval + LoCoMo with a runnable public
  harness. *Not yet run; no numbers claimed until it is.* In a market where
  [vendor benchmarks have failed reproduction](https://www.braintrust.dev/articles/best-ai-agent-memory-tools-2026),
  we will ship the harness before the number.
- **Full FSRS scheduling** (the v1 ladder is deliberately simple).
- **Batch-API judge** for bulk arbitration at 50% pricing.

## Provenance

Nidra generalizes a memory doctrine built and battle-tested inside a production
RAG system for Sanskrit scripture (PuranGPT), where an automatically distilled
memory once fabricated citations — and the cure was exactly this: evidence rows
with exact excerpts and hashes, graded epistemic states, verify-gated promotion,
and a scheduled consolidation pass. The Sanskrit names are not decoration; the
architecture is older than computers. *Saṃskāra* (the impression laid down),
*smṛti* (deliberate remembrance), *nidrā* (the sleep in which the mind sorts
what it keeps).

MIT license.
