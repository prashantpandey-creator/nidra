# Nidra — user guide

Nidra keeps an AI's memory honest. Every memory it holds carries the receipt it
came from — the file, the exact sentence, a fingerprint of that sentence — and a
scheduled pass re-checks every receipt against the real world. When a source
changes, the memory that depended on it loses its badge and stops being trusted.

Nothing leaves your machine, and nothing needs an API key.

---

## Before you start

One thing only:

- **Python 3.9 or newer** — check with `python3 --version`

That's the whole list. Nidra has no dependencies. The optional judge (below)
uses Claude Code if you already have it; it is never required.

---

## 1. Install

You'll be given a file called something like **`nidra-0.1.0.zip`**. Two steps,
once per machine.

**Step one — unzip it.** Right-click → Extract All (Windows), or double-click
(Mac). You'll get a folder with three things in it:

| What you'll see | What it is |
|---|---|
| `install.cmd` | **The Windows installer.** Use this one on Windows. |
| `install.sh` | **The Mac and Linux installer.** Use this one on a Mac or Linux. |
| `runtime` | Nidra itself. The installer handles it. |

**Step two — run the installer for your computer.**

- **On Windows:** double-click **`install.cmd`**.
- **On Mac or Linux:** open a terminal in that folder and run **`./install.sh`**.

It takes a second. It never asks for an administrator password.

**Step three — close your terminal and open a new one.** The `nidra` command
only appears in terminals opened after the install.

You can delete the unzipped folder now; Nidra has copied what it needs.

---

## 2. See it work, in thirty seconds

```
nidra demo
```

This is the whole argument for Nidra, run in front of you. It builds a small
memory store with **known defects planted in it** — duplicates, contradictions,
stale junk, and one memory that is correctly verified and whose source file then
changes behind its back. It runs two nights of sleep, and checks that every
planted defect was caught:

```
  [PASS] duplicate pair merged
  [PASS] good memory promoted to machine_checked
  [PASS] numeric + negation contradictions flagged
  [PASS] overdue junk tombstoned
  [PASS] stale verified memory demoted after source change
  [PASS] third pass is a no-op (idempotent)
```

Nothing is written outside the demo folder, and it costs nothing.

---

## 3. Everything you need to do, in order

| | Do this | Why |
|---|---|---|
| 1 | `cd /path/to/your-project` | Nidra works on one store at a time |
| 2 | `nidra init` | Creates the store here. Free, instant |
| 3 | `nidra add "..." --source f.md --excerpt "..."` | Put a memory in, with its receipt |
| 4 | `nidra sleep --report trust-report.md` | The nightly pass. Free |
| 5 | `nidra why <id>` | Ask any memory to prove itself, live |

---

## 4. Adding a memory with its receipt

```
nidra add "The service listens on port 8000" \
    --subject service-port \
    --source docs/deploy.md \
    --excerpt "listens on port 8000"
```

- `--source` is the file the fact came from.
- `--excerpt` is the **exact text** in that file which supports it. Nidra stores
  a fingerprint of it, and re-checks it later.
- `--subject` groups memories that talk about the same thing, so contradictions
  between them can be found.

A memory added without a source is allowed — it is simply graded `unverified`,
which is the honest word for "nobody has checked this."

---

## 5. The nightly pass

```
nidra sleep --report trust-report.md
```

Five things happen, all of them free and none of them calling a model:

1. **Duplicates merge** — same statement, one memory, receipts combined.
2. **Receipts get re-checked** against the real files. This is the heart of it:
   a memory whose source changed is **demoted**, however confident it was.
3. **Contradictions are flagged** — two memories about one subject that disagree.
4. **Reviews are scheduled** — memories that keep checking out are re-checked
   less often (1, 3, 7, 14, 30, 90 days); a failure resets the clock.
5. **Dead weight is tombstoned** — never deleted; the journal keeps everything.

Run it nightly from `cron` or Task Scheduler and forget about it. Running it
twice on an unchanged store does nothing at all — that's deliberate.

### The three grades

| Grade | What it means |
|---|---|
| `unverified` | No receipt, or a receipt that failed its last check |
| `source_linked` | Has a receipt, but the source can't be re-read right now |
| `machine_checked` | Receipt re-verified against the real file this pass |

---

## 6. Ask a memory to prove itself

```
nidra why mem_a1b2c3d4e5f6
```

Prints the memory, its receipts, their fingerprints — and then **re-reads the
source files right now** in front of you, saying for each one whether the text
is still there. You never have to take Nidra's word for anything.

---

## 7. Optional: settling arguments

When two memories about the same subject contradict each other, Nidra flags them
and leaves them alone. If you'd like a model to arbitrate:

```
nidra sleep --judge
```

This uses **Claude Code** if you have it installed and signed in — your own
subscription, no API key, nothing to configure. If Claude Code isn't there, or
isn't logged in, nothing breaks: the pair simply stays flagged for you to decide.

---

## 8. Importing what you already have

If you use **MemPalace**:

```
nidra import-mempalace --room decisions
nidra sleep --report trust-report.md
```

It reads the palace strictly read-only and turns drawers into graded memories
pointing back at the original transcripts. Expect a surprise: on the first real
archive we tried this on, **over half the receipts pointed at files that no
longer existed.** That is what memory rot looks like when someone finally
measures it.

---

## Where your data lives

One folder, wherever you ran `nidra init` (`.nidra` by default):

- `memories.jsonl` — one memory per line, plain readable JSON
- `journal.jsonl` — every change ever made, so nothing is unexplained

**Nidra makes no network calls of its own.** Read the files, copy them, delete
them — they're yours, in a format you can open in any text editor.

---

## Uninstall

Delete two things:

- `~/.nidra-app` (Mac/Linux) or `%USERPROFILE%\.nidra-app` (Windows)
- the `nidra` command in `~/.local/bin`

Your stores stay where they are, readable without Nidra. No package manager was
involved; there is nothing else on your machine.
