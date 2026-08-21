"""Tests for nidra.adapters.memory_files — grading .md memory files."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nidra.adapters.memory_files import (
    _best_anchor,
    _extract_paths,
    _extract_wikilinks,
    _parse_frontmatter,
    file_to_memory,
    import_memory_files,
)
from nidra.store import Store


class TestParseFrontmatter(unittest.TestCase):
    def test_with_frontmatter(self):
        text = '---\nname: test-mem\ndescription: "a test"\nmetadata:\n  type: project\n---\nBody here.'
        fm, body = _parse_frontmatter(text)
        self.assertEqual(fm["name"], "test-mem")
        self.assertEqual(fm["description"], "a test")
        self.assertEqual(body, "Body here.")

    def test_without_frontmatter(self):
        text = "Just a body."
        fm, body = _parse_frontmatter(text)
        self.assertEqual(fm, {})
        self.assertEqual(body, "Just a body.")


class TestExtractPaths(unittest.TestCase):
    def test_absolute_paths(self):
        text = "The file at /Users/badenath/projects/foo.py is important."
        paths = _extract_paths(text)
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0][0], "/Users/badenath/projects/foo.py")

    def test_tilde_paths(self):
        text = "Check ~/projects/nidra/nidra/store.py for details."
        paths = _extract_paths(text)
        self.assertEqual(len(paths), 1)
        self.assertTrue(paths[0][0].endswith("projects/nidra/nidra/store.py"))
        self.assertFalse(paths[0][0].startswith("~"))

    def test_no_paths(self):
        text = "No paths here, just words."
        self.assertEqual(_extract_paths(text), [])

    def test_path_cleanup(self):
        text = "See /Users/foo/bar.py. And /Users/foo/baz.py:"
        paths = _extract_paths(text)
        self.assertEqual(len(paths), 2)
        self.assertFalse(paths[0][0].endswith("."))
        self.assertFalse(paths[1][0].endswith(":"))


class TestExtractWikilinks(unittest.TestCase):
    def test_simple_link(self):
        text = "Related: [[some-memory]]"
        links = _extract_wikilinks(text)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0][0], "some-memory")

    def test_link_with_alias(self):
        text = "See [[target-name|display text]]."
        links = _extract_wikilinks(text)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0][0], "target-name")

    def test_gap_skipped(self):
        text = "There is a [[GAP]] here."
        links = _extract_wikilinks(text)
        self.assertEqual(len(links), 0)


class TestBestAnchor(unittest.TestCase):
    def test_picks_longest_line(self):
        body = "# Heading\nShort.\nThis is a much longer line that should be picked as the anchor for verification."
        anchor = _best_anchor(body)
        self.assertIn("much longer line", anchor)

    def test_skips_headings(self):
        body = "# This heading is very long and should not be selected as anchor\nThis body line is long enough to qualify as an anchor for the test."
        anchor = _best_anchor(body)
        self.assertNotIn("heading", anchor)
        self.assertIn("body line", anchor)

    def test_none_if_too_short(self):
        body = "# H\nHi."
        self.assertIsNone(_best_anchor(body))


class TestFileToMemory(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.md_path = os.path.join(self.tmpdir, "test-mem.md")
        with open(self.md_path, "w") as f:
            f.write('---\nname: test-mem\ndescription: "A test memory about /Users/foo/bar.py"\nmetadata:\n  type: project\n---\n')
            f.write("This memory references /Users/foo/bar.py and [[other-mem]].\n")
            f.write("It also has a long line for the content anchor that should be verifiable.\n")

    def test_memory_shape(self):
        mem, stats = file_to_memory(self.md_path, self.tmpdir)
        self.assertEqual(mem["subject"], "memory:test-mem")
        self.assertIn("memory-file", mem["tags"])
        self.assertIn("type:project", mem["tags"])

    def test_evidence_rows(self):
        mem, stats = file_to_memory(self.md_path, self.tmpdir)
        self.assertGreater(len(mem["evidence"]), 0)
        locators = [e["locator"] for e in mem["evidence"]]
        has_path = any("path:" in l for l in locators)
        has_wiki = any("wikilink:" in l for l in locators)
        has_content = any("content_anchor" in l for l in locators)
        self.assertTrue(has_path)
        self.assertTrue(has_wiki)
        self.assertTrue(has_content)

    def test_stats(self):
        _, stats = file_to_memory(self.md_path, self.tmpdir)
        self.assertGreater(stats["paths"], 0)
        self.assertGreater(stats["wikilinks"], 0)
        self.assertGreater(stats["content"], 0)

    def test_id_stable(self):
        mem1, _ = file_to_memory(self.md_path, self.tmpdir)
        mem2, _ = file_to_memory(self.md_path, self.tmpdir)
        self.assertEqual(mem1["id"], mem2["id"])


class TestImportMemoryFiles(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store_dir = os.path.join(self.tmpdir, "store")
        self.mem_dir = os.path.join(self.tmpdir, "memory")
        os.makedirs(self.mem_dir)
        self.store = Store(self.store_dir)
        self.store.init()

        for i in range(3):
            with open(os.path.join(self.mem_dir, f"mem-{i}.md"), "w") as f:
                f.write(f"---\nname: mem-{i}\ndescription: Memory number {i} about some topic\nmetadata:\n  type: project\n---\n")
                f.write(f"This is memory {i} with enough text to form a content anchor for verification.\n")

    def test_imports_all(self):
        result = import_memory_files(self.store, self.mem_dir)
        self.assertEqual(result["scanned"], 3)
        self.assertEqual(result["imported"], 3)

    def test_idempotent(self):
        import_memory_files(self.store, self.mem_dir)
        result = import_memory_files(self.store, self.mem_dir)
        self.assertEqual(result["imported"], 0)
        self.assertEqual(result["already_exists"], 3)

    def test_store_grows(self):
        import_memory_files(self.store, self.mem_dir)
        mems = self.store.load()
        self.assertEqual(len(mems), 3)
        for m in mems:
            self.assertTrue(m["id"].startswith("mem_"))
            self.assertGreater(len(m["evidence"]), 0)

    def test_journal_logged(self):
        import_memory_files(self.store, self.mem_dir)
        with open(self.store.journal_path) as f:
            events = [json.loads(l) for l in f if l.strip()]
        import_events = [e for e in events if e.get("event") == "import.memory_files"]
        self.assertEqual(len(import_events), 1)
        self.assertEqual(import_events[0]["scanned"], 3)

    def test_skips_MEMORY_md(self):
        with open(os.path.join(self.mem_dir, "MEMORY.md"), "w") as f:
            f.write("# Index\n- [mem-0](mem-0.md)\n")
        result = import_memory_files(self.store, self.mem_dir)
        self.assertEqual(result["scanned"], 3)


class TestRealMemoryFiles(unittest.TestCase):
    """Run against actual memory files if they exist."""

    REAL_DIR = os.path.expanduser(
        "~/claude-sync/memory/-Users-badenath-projects-vedic-puran"
    )

    @unittest.skipUnless(
        os.path.isdir(os.path.expanduser("~/claude-sync/memory/-Users-badenath-projects-vedic-puran")),
        "real memory dir not present"
    )
    def test_real_files_parse(self):
        count = 0
        errors = []
        for fname in os.listdir(self.REAL_DIR):
            if not fname.endswith(".md") or fname == "MEMORY.md":
                continue
            filepath = os.path.join(self.REAL_DIR, fname)
            try:
                mem, stats = file_to_memory(filepath, self.REAL_DIR)
                self.assertTrue(mem["id"].startswith("mem_"))
                self.assertTrue(len(mem["statement"]) > 0)
                count += 1
            except Exception as e:
                errors.append(f"{fname}: {e}")
        self.assertGreater(count, 200)
        self.assertEqual(len(errors), 0, f"Parse errors: {errors}")


if __name__ == "__main__":
    unittest.main()
