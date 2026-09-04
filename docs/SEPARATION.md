# The seam audit: nidra, CLAUD-E, and meditate

Audited 2026-09-04 against nidra `d214005` (0.1.0 on PyPI), CLAUD-E `df7070e`
(the digital twin, the repo called `meditate` until 2026-09-04), and
meditate-sessions `a2819ea` (0.12.0, the shipped session product). Nothing in
this document changes behaviour. It is the record the separation work is
measured against; every claim was checked in the code, with the file and line
beside it.

## The question, and the short answer

"Separate nidra into meditate and the digital twin." The three repos already
answer most of it:

- **meditate-sessions takes nothing from nidra, by decision.** It is generated
  by CLAUD-E's `release.py` from six entry modules (`release.py:63`), and the
  2026-09-02 release commit cut the grading half: "graded memory is the
  COMPANION's pitch", and keeping it made the product's stdlib-only claim
  false. The product imports zero nidra symbols.
- **CLAUD-E is nidra's only consumer.** It pip-installs `nidra-agent-memory`
  pinned to `>=0.1.0,<0.2.0` (`install.sh:209`), with a git clone of this repo
  as the fallback (`install.sh:211`). Its README calls the engine "a small
  internal library" that "lives in its own repo only so it can be tested in
  isolation."
- **What is left inside nidra that is not engine is twin.** Two adapters, the
  twin's directory layout inside the grader, and the twin's on-disk
  conventions that the engine never gave an API for.

So the work is not a two-way split. It is: move the twin's adapters into
CLAUD-E, make the engine layout-agnostic, give the twin a Store API so it stops
rewriting the engine's files by hand, and scrub the meditate product's leftover
engine references. Dissolving nidra into CLAUD-E is the wrong move, for the
reasons at the end.

## What CLAUD-E actually uses

Eight symbols from five modules, in four files:

| nidra symbol | CLAUD-E consumer |
|---|---|
| `Store`, `new_memory`, `sha256_text` | `nidra_bridge.py`, `formation.py` |
| `run_sleep`, `census` | `nidra_bridge.py` |
| `retrieve` | `ask.py`, `coordination.py` (the latter with an inline tf-idf fallback) |
| `import_sessions` | `nidra_bridge.py` |
| `import_memory_files` | `nidra_bridge.py` |

Never touched: `grade()` or `verify_evidence_row` directly, `recall`, the
judge, the Claude CLI bridge, the eval harness, the MemPalace adapter, the
`nidra` command. (`ask.py:112` names `nidra.grade` in a comment only.)

Touched everywhere: the files. Thirteen CLAUD-E files open `memories.jsonl` or
`journal.jsonl` directly (`archive`, `ask`, `coordination`, `doctor`,
`freshcheck`, `goals`, the hook, `install.sh`, `metrics`, `nidra_bridge`,
`projects`, `report`, `uninstall.sh`), and the bridge implements a store lock
(`nidra_bridge.py:108`), journal rotation (`:69`), and a path index (`:214`)
on top of nidra's format. The engine has none of those.

## Where each piece of nidra belongs

| nidra code | belongs to | consumed today by | lines |
|---|---|---|---:|
| `store`, `grade`, `sleep`, `report`, `judge`, `claude_cli`, `retrieval`, `cli` | engine, stays | CLAUD-E: store, sleep, retrieval | 1,267 |
| `adapters/meditate.py` | twin | only `nidra_bridge.py` | 124 |
| `adapters/memory_files.py` | twin | only `nidra_bridge.py` | 424 |
| `recall.py` | engine, optional | nobody in either product | 153 |
| `adapters/mempalace.py`, `eval/` | engine, neutral | README dogfood and the benchmark | 545 |
| tests for the two twin adapters, the extractor corpus, its fixtures | twin, moves with them | | 899 |
| meditate-sessions | nothing | imports zero nidra symbols by design | 0 |

`tests/test_world_evidence.py` is mixed: the scope and git-verification classes
belong to the engine; `TestGitClaimExtraction`, `TestMultiRepoGitClaims` and
`TestAllDigitShaIsDeliberatelyRefused` exercise the memory-files extractor and
move with it.

## The seams

Each is verified against the code. Two are reproduced below.

1. **The grader hardcodes the twin's layout.** `nidra/grade.py:167` fixes
   `DEFAULT_STORE_ROOTS` to `~/claude-sync/memory` and `~/.claude/meditation`,
   and `run_sleep` (`sleep.py:94`) calls `evidence_scope(m)` at `:155` and
   `:170` with no way to pass roots. CLAUD-E's `paths.py` resolves the memory
   root four ways: environment, a recorded path, `~/claude-sync/memory` or
   `~/.claude/memory`, then a default. A claim under `~/.claude/memory` or
   under `MEDITATE_MEMORY_ROOT` is classed `world`, so the world-decidable
   figure this repo corrected from 56% to 13% (`dcaabb4`) is inflated on any
   machine using those roots.

2. **The memory-files extractor claims only macOS paths, and grades foreign
   homes as drift.** `memory_files.py:155`, `:166` and the regexes at `:169`
   accept `/Users/` and `~/` only. A `/home/user/...` path yields no claim, so
   a Linux twin reports full coverage with zero path claims; CLAUD-E's CI runs
   on `macos-latest` and never sees it, while its README promises Linux. The
   other half: `grade.py:136` grades a `path:` claim whose target is absent as
   `drifted`. The twin's memory root is a sync folder, so a memory file citing
   `/Users/<name>/...` is correct on one machine and "drifted" on every other.
   By this repo's own rule, the absence of another user's home decides nothing.

3. **The twin's repair-queue filename sits inside a nidra adapter.**
   `memory_files.py:78`.

4. **A core helper lives in the wrong adapter.** `clean_anchor` is defined in
   `adapters/mempalace.py:52` and imported by `adapters/meditate.py:18` and
   `eval/longmemeval.py:34`. Moved to CLAUD-E as-is, the session adapter would
   import from an adapter for a tool the twin does not use.

5. **The twin owns the engine's file format by convention.** Locking, journal
   rotation, evidence retargeting on archive (`archive.py:92`) and the path
   index are all implemented outside nidra against its jsonl layout. Any change
   to the store format breaks the twin silently.

6. **The meditate product still ships engine residue.** meditate-sessions
   `SKILL.md:64` and `:73-79` tell the user to run `nidra_bridge.py` and
   `test_nidra_bridge.py`, which are not shipped; `release.py`'s doc filter
   (`:248`, `:268`) strips `twin`, `CLAUD-E`, `casper` and `mascot` and nothing
   else. `archive.py:92` rewrites the engine's memories file under the engine's
   lock when a store exists, and with `--apply` creates the store directory and
   lock file (`:163`) even when no engine is installed. `paths.py:141` hunts
   for a nidra checkout. A stdlib-only product carries a private-format writer
   for a library it says it does not use.

7. **nidra's README is a release behind its code.** It never mentions the two
   adapters, `evidence_scope`, valid time or `git:` evidence, and its roadmap
   still lists file-store adapters as open. CLAUD-E's README documents nidra's
   adapters instead.

8. **Personal machine paths sit in nidra's tests.**
   `tests/test_meditate_adapter.py:3` names the author's checkout;
   `tests/test_memory_files_adapter.py:40`, `:190`, `:194` and `:215` name the
   author's memory directory, and two tests skip everywhere else. CLAUD-E's
   own `test_product.py` forbids exactly this class.

9. **The move is a breaking release.** CLAUD-E pins below 0.2.0. Removing the
   adapters from the package needs 0.2.0, a pin bump, and an order of
   operations.

10. **Three vocabularies for one thing.** `sleep.py` calls the pass "the
    meditation"; the twin's directory is `~/.claude/meditation`; the store is
    `nidra_store` inside it; `nidra init` prints "initialized palace".

### Reproductions

From this checkout on a Linux machine (home is `/root` in the run below):

    python3 - <<'PY'
    from nidra.adapters.memory_files import _extract_paths
    from nidra.grade import evidence_scope
    import os
    print(_extract_paths("the guard lives in /home/user/nidra/nidra/store.py today"))
    row = lambda p: {"locator": "path:" + p, "source": "x", "excerpt": "y", "sha256": "z"}
    print(evidence_scope({"evidence": [row(os.path.expanduser("~/.claude/memory/a.md"))]}))
    PY

Output on 2026-09-04:

    []
    world

The first line should be one claim. The second should be `internal`.

## The work, in order

### nidra (this repo)

1. **Move `clean_anchor` into core** (`store.py`, or a new `anchor.py`) and
   keep the re-export in the MemPalace adapter. Small.
2. **Make store roots injectable.** `run_sleep(..., store_roots=None)` threads
   through to `evidence_scope`; the default stays `DEFAULT_STORE_ROOTS`, and a
   colon-separated `NIDRA_STORE_ROOTS` environment variable overrides it so the
   twin's heartbeat needs no code change. Small.
3. **Three-valued path claims.** In `grade.py:136`, a `path:` target under a
   home directory that is not this machine's is `source_missing` (not
   checkable), never `drifted`. Small.
4. **A Store API for what the twin does by hand:** `Store.lock()` as a context
   manager on the same `.grade.lock` file the twin already uses, so mixed
   versions coexist; `Store.rotate_journal(max_bytes)`;
   `Store.retarget_source(old, new)` with a journal event. Optional:
   `Store.claims_by_path()` returning what the twin writes as
   `path_index.json`. Medium.
5. **Scrub personal paths from tests**, and put the real-corpus checks behind
   a `NIDRA_REAL_MEMORY_DIR` environment variable. Small.
6. **README to match the code**, then cut 0.2.0 once the adapters have their
   new home. Small.

### CLAUD-E

7. **Adopt the two adapters** as flat modules in its own convention
   (`adapter_sessions.py`, `adapter_memory_files.py`) with their tests and
   `fixtures/memory_corpus/`; the extractor learns the running user's home
   prefix, with a Linux fixture added to the corpus (seam 2, first half).
   `nidra_bridge.py` imports the local copies first and falls back to nidra's
   while both exist. Nothing in `release.py`'s `ENTRY` imports them, so the
   product closure excludes them by construction. Medium.
8. **Replace direct jsonl access** in the thirteen files with the Store API
   from item 4, then raise the pin to `>=0.2,<0.3` and drop the fallback.
   Medium to large.
9. **Product hygiene in `release.py`:** extend the doc filter to strip `nidra`
   lines; put `archive.py`'s retargeting behind a guarded engine import so the
   product carries no engine-format writer and creates no engine directories;
   add a `test_product.py` assertion that no shipped module names nidra;
   regenerate meditate-sessions. Small.

### Order of releases

1. CLAUD-E item 7. It works against 0.1.0 and 0.2.0 alike.
2. nidra items 1 to 6, released as 0.2.0 with the adapters removed.
3. CLAUD-E items 8 and 9, with the pin bump.

## What not to do

- **Do not dissolve nidra into CLAUD-E.** It is published and tagged (PyPI
  0.1.0, `v0.1.0`); its README, `LAUNCH.md` and CI proof stand alone; the
  MemPalace adapter and the LongMemEval harness have no twin consumer; and
  CLAUD-E's own README keeps the engine apart for isolated testing.
- **Do not split the engine's core along store-versus-pass lines.** The
  dependency is one-way (`sleep` imports `grade` and `store`), so it is
  possible, but nothing consumes the halves separately.
