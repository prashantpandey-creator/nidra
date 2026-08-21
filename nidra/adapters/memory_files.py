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


def _extract_paths(text: str) -> List[Tuple[str, str]]:
    """Extract (path, containing_line) pairs from text."""
    results = []
    for line in text.splitlines():
        for m in re.finditer(r"(?<!\w)(/Users/[^\s\)\]\>\,\;\"'`]+)", line):
            p = m.group(1).rstrip(".:`)>")
            if len(p) > 10:
                results.append((p, line.strip()))
        for m in re.finditer(r"(?<!\w)(~/[^\s\)\]\>\,\;\"'`]+)", line):
            p = m.group(1).rstrip(".:`)>")
            if len(p) > 5:
                results.append((os.path.expanduser(p), line.strip()))
    return results


def _extract_wikilinks(text: str) -> List[Tuple[str, str]]:
    """Extract ([[target]], containing_line) pairs."""
    results = []
    for line in text.splitlines():
        for m in re.finditer(r"\[\[([^\]\|]+?)(?:\|[^\]]+)?\]\]", line):
            target = m.group(1).strip()
            if target and target != "GAP":
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
            seen = {(e.get("source"), e.get("excerpt")) for e in target["evidence"]}
            added = 0
            for ev in mem["evidence"]:
                if (ev.get("source"), ev.get("excerpt")) not in seen:
                    target["evidence"].append(ev)
                    added += 1
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
