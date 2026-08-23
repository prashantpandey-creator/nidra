"""nidra.adapters.memory_files — grade the user's .md memory files for drift.

The user's real knowledge lives in hand-curated .md files (244 files, 1.2 MB),
not in session transcripts. Each file contains verifiable claims: file paths,
wikilinks, function references, env flags. This adapter extracts those claims,
builds SHA-256 evidence receipts, and imports them into nidra's graded store.

At serve time, nidra's grade.py re-checks each evidence row:
  - Does the file path still exist on disk?
  - Does the wikilink still resolve to a .md file?
  - Does the excerpt still appear in the source?

When something drifts — a file deleted, a path renamed, a link broken — the
memory silently stops serving. That is the whole point.

Evidence types:
  - path_exists:   /Users/.../file.py or ~/path → check os.path.exists()
  - wikilink:      [[name]] → check name.md exists in memory dir
  - content_anchor: text excerpt from the .md file itself → SHA-256

The .md file body IS the source for content anchors. A path claim's source is
the .md file; the excerpt is the line containing the path. When grade.py
re-checks, it reads the .md file and looks for the excerpt — if the memory
was edited to remove that claim, the evidence drifts. Correct.
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

from ..store import Store, new_memory, sha256_text

STATEMENT_CAP = 600
ANCHOR_MIN = 20
ANCHOR_MAX = 200

# Max path- and wikilink-claims graded per memory file. This was 5, which
# silently dropped 129 real claims across 41 of 272 files (15%) while the
# docs promised "every file path, every wikilink is verified". Measured
# worst case in the real corpus: 8 paths, 26 wikilinks — 40 leaves headroom
# and still bounds a pathological file.
MAX_CLAIMS = 40


def _parse_frontmatter(text: str) -> Tuple[Dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    fm_block = text[3:end].strip()
    body = text[end + 4:].strip()
    fm = {}
    for line in fm_block.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"').strip("'")
    return fm, body


# A path is only a CHECKABLE CLAIM if it names one real location. Templates,
# globs and elided displays are illustrations — asserting they exist and then
# reporting them as drift is the instrument lying, not the world changing.
# Measured on the real corpus: 11 of 25 repair-queue items were this.
_NOT_A_CLAIM = ("<", ">", "{", "}", "*", "?", "\u2026", "...", "$", "%s")
_PLACEHOLDER_WORDS = ("YYYYMMDD", "YYYY-MM-DD", "HHMMSS", "<id", "<ver")

# The repair queue's OWN file is unlinked when the queue is empty and
# recreated the moment a memory fails — including this memory, when it
# mentions the queue's own path. A memory citing it can never settle: passing
# deletes the file (its own evidence target), which fails the memory, which
# recreates the file, which passes the memory again. Measured 2026-08-23:
# mem_75bd7f8c0833 oscillated demoted/regraded 4 times in 90 minutes before
# this exclusion. This is item #1's bug (illustration, not location) in a
# form substring matching couldn't catch: a real path that is the grading
# pipeline's own moving part, not a durable fact about the world.
_SELF_REFERENTIAL_PATHS = ("/.claude/meditation/repair-queue.md",)

# A memory that RECORDS a deletion ("the plan file X is gone") states a fact
# about absence. Grading it as "X should exist" marks the memory drifted for
# being correct — the exact inversion of the tool's purpose. Measured: 2 of
# the 24 remaining queue items. These are existence claims only; a line like
# "removed the retry from foo.py" keeps its claim (the test pins both ways).
_ABSENCE_PHRASES = (
    "is gone", "are gone", "now gone", "was deleted", "were deleted",
    "was removed", "were removed", "no longer exists", "does not exist",
    "doesn't exist", "not installed", "decommissioned", "is dead",
    "was retired", "never existed", "don't recreate", "do not recreate",
    # "since removed" / "since deleted" is the natural phrasing a person
    # reaches for when repairing a memory in place — and the phrasing this
    # tool's own repair prompt recommends. Missing it meant a memory that had
    # just been correctly repaired would drift again on the next pass.
    # Caught by the fixture corpus, not by a user's token bill.
    "since removed", "since deleted", "since retired", "since gone",
)


def _is_derived(locator: str) -> bool:
    """True for evidence this adapter generates from the .md file itself."""
    return (locator.startswith("path:") or locator.startswith("wikilink:")
            or locator == "content_anchor")


def _is_checkable(p: str) -> bool:
    """False for anything that is an illustration rather than a location."""
    if any(t in p for t in _NOT_A_CLAIM):
        return False
    if any(w in p for w in _PLACEHOLDER_WORDS):
        return False
    if any(s in p for s in _SELF_REFERENTIAL_PATHS):
        return False
    return True


def _states_absence(line: str) -> bool:
    low = line.lower()
    return any(ph in low for ph in _ABSENCE_PHRASES)


def _path_head(span: str) -> str:
    """The path part of a backticked span, dropping any command tail.

    `~/t/run.sh --human` -> `~/t/run.sh`. A path may contain spaces (that is
    why the backtick pass exists at all), so we keep consuming words until a
    word that cannot be part of a filename: a flag, or a shell operator.
    """
    words, out = span.split(), []
    for w in words:
        if w.startswith("-") or w in ("|", "&&", "||", ";", ">", ">>", "<"):
            break
        out.append(w)
    return _clean(" ".join(out) or span)


def _clean(p: str) -> str:
    p = p.strip().rstrip(".:`)>")
    # a trailing :NN is a line reference — the FILE is the claim
    return re.sub(r":\d+$", "", p)


def _extract_paths(text: str) -> List[Tuple[str, str]]:
    """Extract (path, containing_line) pairs of CHECKABLE paths only."""
    results = []
    for line in text.splitlines():
        if _states_absence(line):
            continue
        found, spans = [], []
        # Backticks delimit a path unambiguously, so a backticked path MAY
        # contain spaces. Without this pass the bare regex stopped at the
        # first space and claimed `~/Documents/travel` — a directory that
        # never existed — while the real `travel website/` sat right there.
        for m in re.finditer(r"`([^`]+)`", line):
            inner = _clean(m.group(1))
            if inner.startswith("/Users/") or inner.startswith("~/"):
                # A backticked span may be a COMMAND, not just a path. Spaces
                # are allowed inside a path; flags and shell operators are not.
                # Without this, `preflight.sh --human` was claimed verbatim and
                # reported as missing — the script was right there.
                found.append(_path_head(inner))
                spans.append((m.start(), m.end()))
            else:
                # A path can also appear as an ARGUMENT inside a command span
                # (`cat ~/tools/list.txt | head`). Claim the path, not the line.
                for tok in inner.split():
                    if tok.startswith("/Users/") or tok.startswith("~/"):
                        found.append(_clean(tok))
                spans.append((m.start(), m.end()))
        for pat in (r"(?<!\w)(/Users/[^\s\)\]\>\,\;\"'`]+)",
                    r"(?<!\w)(~/[^\s\)\]\>\,\;\"'`]+)"):
            for m in re.finditer(pat, line):
                # skip anything the backtick pass already claimed
                if any(s <= m.start() < e for s, e in spans):
                    continue
                found.append(_clean(m.group(1)))
        for p in found:
            full = os.path.expanduser(p)
            if len(full) > 10 and _is_checkable(full):
                results.append((full, line.strip()))
    return results


def _extract_wikilinks(text: str) -> List[Tuple[str, str]]:
    """Extract ([[target]], containing_line) pairs."""
    results = []
    for line in text.splitlines():
        # A wikilink inside backticks is quoted SYNTAX being described, not a
        # link to follow — the mirror of the backtick rule for paths.
        code = [(m.start(), m.end()) for m in re.finditer(r"`[^`]+`", line)]
        for m in re.finditer(r"\[\[([^\]\|]+?)(?:\|[^\]]+)?\]\]", line):
            if any(s <= m.start() < e for s, e in code):
                continue
            target = m.group(1).strip()
            # [[#heading]] is an in-document anchor, not a memory file.
            if not target or target == "GAP" or target.startswith("#"):
                continue
            # [[name.md]] and [[name]] point at the SAME file. Appending .md
            # blindly produced name.md.md and reported a live memory as a
            # broken link — 4 of 16 remaining queue items were this.
            if target.endswith(".md"):
                target = target[:-3]
            results.append((target, line.strip()))
    return results


def _best_anchor(body: str) -> Optional[str]:
    """Pick the richest line from the body as a content anchor."""
    best = ""
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("#") or line.startswith("---") or not line:
            continue
        if len(line) > len(best):
            best = line
    if len(best) >= ANCHOR_MIN:
        return best[:ANCHOR_MAX]
    return None


def file_to_memory(
    filepath: str,
    memory_dir: str,
) -> Tuple[Dict[str, Any], Dict[str, int]]:
    """Convert one .md memory file into a nidra memory with evidence.

    Returns (memory_dict, stats) where stats counts evidence types found.
    """
    with open(filepath, encoding="utf-8") as fh:
        text = fh.read()
    fm, body = _parse_frontmatter(text)

    name = fm.get("name", os.path.splitext(os.path.basename(filepath))[0])
    desc = fm.get("description", "")
    mem_type = fm.get("type", "")
    if not mem_type:
        for line in text[:500].splitlines():
            if "type:" in line:
                for t in ("feedback", "project", "reference", "user"):
                    if t in line:
                        mem_type = t
                        break

    statement = desc[:STATEMENT_CAP] if desc else body[:STATEMENT_CAP]
    if not statement.strip():
        statement = name

    tags = ["memory-file", f"type:{mem_type or 'unknown'}"]

    mem = new_memory(
        statement,
        subject=f"memory:{name}",
        tags=tags,
        confidence=0.9,
    )
    mem["id"] = "mem_" + sha256_text(f"memfile|{name}")[:12]

    stats = {"paths": 0, "wikilinks": 0, "content": 0}

    paths = _extract_paths(body)
    for path, line in paths[:MAX_CLAIMS]:
        mem["evidence"].append({
            "source": filepath,
            "excerpt": line[:ANCHOR_MAX],
            "sha256": sha256_text(line[:ANCHOR_MAX]),
            "locator": f"path:{path}",
            "checked_at": None,
        })
        stats["paths"] += 1

    wikilinks = _extract_wikilinks(body)
    for target, line in wikilinks[:MAX_CLAIMS]:
        target_path = os.path.join(memory_dir, target + ".md")
        mem["evidence"].append({
            "source": target_path,
            "excerpt": target,
            "sha256": sha256_text(target),
            "locator": f"wikilink:[[{target}]]",
            "checked_at": None,
        })
        stats["wikilinks"] += 1

    anchor = _best_anchor(body)
    if anchor:
        mem["evidence"].append({
            "source": filepath,
            "excerpt": anchor,
            "sha256": sha256_text(anchor),
            "locator": "content_anchor",
            "checked_at": None,
        })
        stats["content"] += 1

    return mem, stats


def import_memory_files(
    store: Store,
    memory_dir: str,
) -> Dict[str, Any]:
    """Bulk-import .md memory files into the nidra store."""
    memory_dir = os.path.expanduser(memory_dir)
    if not os.path.isdir(memory_dir):
        return {"scanned": 0, "imported": 0, "error": f"not a directory: {memory_dir}"}

    existing = {m["id"]: m for m in store.load()}
    summary = {
        "scanned": 0,
        "imported": 0,
        "already_exists": 0,
        "no_evidence": 0,
        "total_evidence_rows": 0,
        "by_type": {"paths": 0, "wikilinks": 0, "content": 0},
    }
    fresh: Dict[str, Dict[str, Any]] = {}

    for fname in sorted(os.listdir(memory_dir)):
        if not fname.endswith(".md") or fname == "MEMORY.md":
            continue
        filepath = os.path.join(memory_dir, fname)
        if not os.path.isfile(filepath):
            continue

        summary["scanned"] += 1
        mem, stats = file_to_memory(filepath, memory_dir)

        for k in ("paths", "wikilinks", "content"):
            summary["by_type"][k] += stats[k]
        summary["total_evidence_rows"] += len(mem["evidence"])

        if not mem["evidence"]:
            summary["no_evidence"] += 1

        target = existing.get(mem["id"]) or fresh.get(mem["id"])
        if target is not None:
            # REPLACE the derived rows, don't union them. Unioning meant a
            # claim that entered the store once could never leave: fixing the
            # .md and re-grading still reported the old path as drifted, so
            # the repair loop had no exit. Non-derived evidence (anything a
            # human or another adapter attached) is preserved.
            kept = [e for e in target["evidence"]
                    if not _is_derived(str(e.get("locator", "")))]
            target["evidence"] = kept + mem["evidence"]
            summary["already_exists"] += 1
            continue

        fresh[mem["id"]] = mem
        summary["imported"] += 1

    mems = list(existing.values()) + list(fresh.values())
    store.save(mems)
    store.journal({
        "event": "import.memory_files",
        "memory_dir": memory_dir,
        "scanned": summary["scanned"],
        "imported": summary["imported"],
    })
    return summary
