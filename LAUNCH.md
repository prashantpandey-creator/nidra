# Launch drafts — nidra 0.1.0

Draft only. Nothing here has been posted. Every number was measured on the
real store on 2026-08-23/24 and is cited in the repo's own commit history.

---

## Show HN

**Title** (80 char limit — this is 77, counted, not estimated):

    Show HN: We measured our own AI memory system and 86% of it was unfalsifiable

**Body:**

I built an evidence-graded memory system for AI agents: every memory carries
receipts (a file path, a wikilink, a commit SHA), and a scheduled pass
re-checks them. Facts that stop being true stop being served.

Then I pointed it at itself, and the results were worse than I expected.

**28 of 30 memories flagged as "drifted" had not drifted.** My extractor was
inventing the claims — asserting that `<project-slug>` and `foo-*.tar.gz`
were real paths, treating `file.py:45` as a filename, and marking a memory
broken *for correctly stating that a file was deleted*. Worst of all, derived
evidence was unioned rather than replaced, so a false claim that entered the
store once could never leave: you could fix the memory, re-grade, and still be
told it was broken. The correction loop had no exit.

**Then the metric itself turned out to be flattering me.** I reported 56% of
memories as "world-decidable" — checkable against something outside the store.
Recomputed strictly, it was 14%. I had been counting wikilinks as evidence,
but a wikilink points at another memory in the same store. That proves the
graph is internally consistent, which is exactly the property that can hold
while every statement is false. **86% of the memories I had marked verified
were answerable only to themselves.**

The uncomfortable part is that both bugs were the same mistake at different
altitudes: a checker that cannot say *"I don't know"* will say *"broken"*
instead. Every fix was the same shape — make the check three-valued
(gone / present / not-checkable) and let only *confirmed-false* become work.

You don't have to take any of this on faith:

```bash
pip install nidra-agent-memory
nidra demo --strict
```

Ten seconds, no API key, no config. It plants known defects, runs two sleep
passes with the world changing in between, and exits non-zero if any planted
defect goes uncaught. That command is what gates the release in CI, so the
badge and the demo are the same claim.

Pure stdlib, no dependencies, MIT.

https://github.com/prashantpandey-creator/nidra

Happy to be told what else is wrong with it — that has gone well so far.

---

## r/LocalLLaMA

**Title:**

    I built evidence-graded memory for agents, then measured it: 28 of 30 "drift" alerts were my own tool lying

**Body:**

Agent memory tools mostly advertise token savings. I wanted the opposite
number, so I measured how much of my own store was actually true.

Setup: each memory carries verifiable evidence — a path, a link, a commit —
and a background pass re-checks it. Drift means the memory stops serving.

What the measurement said:

- **28 of 30 "drifted" memories hadn't drifted.** The extractor was
  manufacturing claims: template strings like `<project-slug>`, globs,
  line-number suffixes read as filenames, and memories marked broken for
  correctly recording that something was deleted.
- **A false claim could never leave the store.** Evidence was unioned instead
  of replaced, so fixing the memory and re-grading still reported it broken.
- **Only 14% of memories were checkable against the outside world**, not the
  56% I first reported. I'd been counting internal links as evidence.

A dispatcher was spending ~44k tokens per agent investigating findings that
were false before the agent booted. There's now a precision gate: sample the
queue with `os.path.exists` (microseconds, zero tokens) before spending a
model on it. Below 50% precision it refuses to dispatch and says the grader is
the bug.

The design rule that came out of it: **presence is decidable, absence usually
isn't.** Commit evidence is confirm-only for that reason — finding a SHA
proves it exists; not finding it only proves you looked in the wrong repo.
That one cost two wrong attempts to learn: 14 of 24 "missing" commits were
real, sitting in a repo the memory never named.

```bash
pip install nidra-agent-memory
nidra demo --strict
```

Stdlib only, MIT, works with any agent framework.
https://github.com/prashantpandey-creator/nidra

---

## Notes before posting

- **Do not post to owned social.** Recorded verdict: those accounts have zero
  followers and are a dead channel. Search and these two venues only.
- Post once, then answer comments. HN penalises reposting.
- The strongest thing here is the self-criticism. If a comment finds another
  hole, that is the best possible outcome — say so and fix it in public.
- Numbers to keep exact: 28/30, 14% (not 56%), 86%, 14 of 24, ~44k tokens.
  Every one is in the commit log with the command that produced it.
