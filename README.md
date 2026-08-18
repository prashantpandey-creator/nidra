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

Or, for people who don't live in a terminal: `packaging/build_zip.sh` produces a
32 KB **`nidra-<version>.zip`** with `install.sh` / `install.cmd` inside. Unzip,
double-click the installer, open a new terminal, run `nidra demo`. No pip, no
git, no package manager, no admin password, no API key — Python 3.9+ is the only
prerequisite, and `packaging/USER-GUIDE.md` is written for someone who has never
heard of any of this.

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

### Then the whole palace

Two rooms were the rehearsal. The full audit — **all 558,151 drawers**, every
wing — imported in 39 seconds and graded in one nine-minute sleep pass
(474,779 active memories after 78,324 literal duplicate texts collapsed):

| the whole mind, graded | count | share |
|---|---:|---:|
| still traceable to source bytes (`machine_checked`) | 107,794 | 22.7% |
| source transcript no longer exists (`source_linked`) | 254,884 | 53.7% |
| unverifiable (no escaping-proof anchor, or drifted) | 112,101 | 23.6% |
| — of which **drifted**: source exists, text absent | 2,551 | 0.5% |

Per room, the rot is uneven: `technical` (the biggest room, 323K memories)
keeps 24.8% byte-traceable; `architecture` has lost 78% of its sources. In
plain words: **of everything this half-million-drawer memory remembers, barely
a fifth can still be re-verified against reality, and until this pass, nothing
and nobody knew which fifth.** That sentence is the product.

One methodological note we're proud of: our first run reported 114 drifted
memories. A hand spot-check showed most were *our own artifact* — anchors
polluted by the palace's rendering prefixes and non-ASCII escaping variance —
so the anchor rules got stricter (pure printable ASCII, prefixes stripped),
false drift collapsed to 21 genuine cases, and the spot-check is now a test.
The audit must survive auditing itself.

## LongMemEval — the harness ships before the number

The eval harness is in the box and keyless: `nidra eval-longmemeval` runs the
real pipeline per question — materialize the haystack, ingest turns as
memories with evidence anchors, sleep, retrieve top-k — and reports **evidence
recall@k**: did the top-k retrieved memories include one from a labeled answer
session? Deterministic, no generation, no LLM judge, nothing to dispute.

```bash
# data: huggingface.co/datasets/xiaowu0162/longmemeval
nidra eval-longmemeval --data longmemeval_s.json --workdir lme-work
```

Our run on **longmemeval_s** (all 500 questions; 470 scored, 30 abstention
variants excluded; 72.9s on a laptop; retrieval is a plain stdlib tf-idf —
Nidra is the pipeline under test, not a retriever):

| question type | n | evidence recall@5 |
|---|---:|---:|
| knowledge-update | 72 | **1.000** |
| single-session-assistant | 56 | 0.964 |
| single-session-user | 64 | 0.953 |
| multi-session | 121 | 0.942 |
| temporal-reasoning | 127 | 0.874 |
| single-session-preference | 30 | 0.467 |
| **overall** | **470** | **0.906** |

Two honest notes. First, the weak row is real and expected: preference
questions are paraphrase-heavy, and a lexical scorer misses paraphrase — plug
in an embedding retriever if you need that row. Second, recall definitions
vary across papers; ours is stated above and implemented in ~30 lines you can
read (`nidra/eval/longmemeval.py`), so compare definitions before comparing
numbers. End-to-end QA accuracy needs model calls and is **not claimed yet** —
the harness is public so the number can never precede the machine. The QA
stage is in the box and needs **no API key** — it runs through your own
Claude Code login:

```bash
nidra eval-longmemeval --data longmemeval_s.json --qa   # requires `claude` login
```

It answers strictly from the retrieved memories, judges hypotheses against
gold with abstention handled, batches items per call, and counts anything
unparsed as wrong — a dead bridge produces missing answers, never invented
ones.

Receipts held at benchmark scale too: of 230,739 turns ingested across the
run, 98.9% earned `machine_checked` grades against their materialized sources.

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
6. **Judge** *(optional, and still no API key)* — contested pairs go to a
   pluggable judge. The default bridge is **Claude Code itself**: if the
   `claude` CLI is installed and logged in, `nidra sleep --judge` runs
   judgment through it — zero keys, zero SDKs, billed to the Claude
   subscription you already have. An Anthropic SDK judge remains as explicit
   fallback for keyed servers. Every path fails open: an unreachable judge
   leaves the pair flagged for a human, never guessed.

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

## The recall cache — a cache that can prove it's still valid

The oldest hard problem in caching is invalidation. The oldest hard problem in
AI memory is staleness. **They are the same problem**, and graded memory solves
both at once:

```python
from nidra import Store
from nidra.recall import remember, recall, prewarm

store = Store(".nidra"); store.init()
remember(store, "What is the retry limit?", "It is 5.",
         sources=[("config.md", "retry limit is 5", "config.md#L12")])

recall(store, "What's the retry limit?")     # → hit (fuzzy match, receipts verify)
# ... config.md changes ...
recall(store, "What's the retry limit?")     # → None. Invalidated by reality.
```

A cached answer carries the receipts it was built from and is **re-graded at
serve time**: the moment any source drifts, the entry silently stops serving —
no TTL guesswork, no stale confident answer surviving on a timer. The sleep
pass re-checks the whole cache on schedule; conflicting cached answers to one
question share a subject, so the contradiction stage catches them and recency
prefers the newest. And `prewarm(...)` runs the *known question space* through
any answerer (the Claude Code bridge included) ahead of demand — if you know
what your users ask, answer it before they do, with receipts, and let the
sleep pass keep the pre-cache honest.

This pattern was proven in production before it was named: the RAG system in
our [field notes](docs/FIELD_NOTES_PURANGPT.md) carries per-user memory across
conversations, mined the finite grammar of what seekers actually ask, and
pre-enriches by measured demand. Nidra adds the missing law: **serve only what
still verifies.**

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
- ~~Published eval harness (LongMemEval)~~ — **shipped and run** (evidence
  recall@5 = 0.906 keyless; see the LongMemEval section). Still open: the
  keyed QA-accuracy stage, and LoCoMo. In a market where
  [vendor benchmarks have failed reproduction](https://www.braintrust.dev/articles/best-ai-agent-memory-tools-2026),
  the harness ships before the number — it just did.
- **Full FSRS scheduling** (the v1 ladder is deliberately simple).
- **Batch-API judge** for bulk arbitration at 50% pricing.

Field notes on the production system these lessons came from:
[docs/FIELD_NOTES_PURANGPT.md](docs/FIELD_NOTES_PURANGPT.md).

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
