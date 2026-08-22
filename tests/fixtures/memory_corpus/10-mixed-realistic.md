---
name: mixed-realistic
description: "The shape a real memory actually has — traps and true claims interleaved."
metadata:
  type: project
---
✅ LIVE since 2026-02-11 — the importer runs from /Users/dev/projects/app/import.py
(built in the throwaway worktree ~/wt-import, since removed) and writes to
`~/Application Support/app/store.db`.

⚠️ Do NOT point it at ~/.tool/projects/<slug>/ — that is a template, not a path.
Rotated files match ~/backups/import-*.jsonl.

The bug was at /Users/dev/projects/app/import.py:88; that line is fixed.
Related: [[import-pipeline]], [[store-schema.md]].
