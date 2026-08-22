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

    @unittest.skipUnless(
        os.path.isdir(os.path.expanduser("~/claude-sync/memory/-Users-badenath-projects-vedic-puran")),
        "real memory dir not present"
    )
    def test_cap_drops_nothing_in_the_real_corpus(self):
        """The docs promise EVERY path and wikilink is verified.

        MAX_CLAIMS was 5, which silently dropped 129 claims across 41 real
        files while the README still said "every". If a future file exceeds
        MAX_CLAIMS, this fails loudly instead of quietly under-grading.
        """
        from nidra.adapters.memory_files import (
            MAX_CLAIMS, _extract_paths, _extract_wikilinks, _parse_frontmatter,
        )
        dropped = []
        for fname in os.listdir(self.REAL_DIR):
            if not fname.endswith(".md") or fname == "MEMORY.md":
                continue
            with open(os.path.join(self.REAL_DIR, fname), encoding="utf-8") as fh:
                _, body = _parse_frontmatter(fh.read())
            np, nw = len(_extract_paths(body)), len(_extract_wikilinks(body))
            if np > MAX_CLAIMS or nw > MAX_CLAIMS:
                dropped.append(f"{fname}: {np} paths, {nw} wikilinks > cap {MAX_CLAIMS}")
        self.assertEqual(dropped, [], "cap is silently dropping real claims: %s" % dropped)


class TestIllustrationsAreNotClaims(unittest.TestCase):
    """A template/glob is an ILLUSTRATION, not a checkable location.

    Measured on the real corpus: 11 of 25 repair-queue items were the
    extractor asserting that '<project-slug>' or 'foo-*.tar.gz' should exist
    on disk, then reporting their absence as knowledge drift. The instrument
    was lying, not the world changing.
    """

    def test_templates_globs_ellipses_refused(self):
        from nidra.adapters.memory_files import _extract_paths
        for bad in ("~/.claude/projects/<project-slug>/x.jsonl",
                    "~/backups/engine-*.tar.gz",
                    "~/Library/Developer/{iOS,macOS}",
                    "~/backups/corpora-YYYYMMDD.tar.gz",
                    "~/.claude/projects/98e8d399-\u2026jsonl"):
            self.assertEqual(_extract_paths("see " + bad), [],
                             "claimed an illustration is a real path: " + bad)

    def test_real_paths_and_file_line_refs_still_claim(self):
        from nidra.adapters.memory_files import _extract_paths
        got = _extract_paths("see /Users/x/projects/thing/setup.py here")
        self.assertEqual(len(got), 1)
        # a trailing :NN is a line reference; the FILE is the claim
        got = _extract_paths("bug at /Users/x/projects/thing/app.py:45")
        self.assertTrue(got and got[0][0].endswith("app.py"), got)


class TestNegatedAndSpacedPaths(unittest.TestCase):
    """Two more ways the extractor invented drift, both measured on the corpus.

    1. A path a memory says is GONE was graded as "should exist" — so the
       memory was marked drifted for being CORRECT. 2 of 24 queue items.
    2. The regex stops at whitespace, so `~/Documents/travel website/x` was
       truncated to `~/Documents/travel` and reported missing. 2 items.
    """

    def test_paths_stated_absent_are_not_claims(self):
        from nidra.adapters.memory_files import _extract_paths
        for line in (
            "the plan file `/Users/x/plans/old.md` referenced above is gone.",
            "not installed here; `/Users/x/.config/anthropic/` does not exist",
            "the worktree /Users/x/wt-thing was removed after the merge",
            "/Users/x/compose-hetzner.yml was deleted 2026-06-30 - do not recreate",
        ):
            self.assertEqual(_extract_paths(line), [],
                             "graded a path the memory says is GONE: " + line)

    def test_ordinary_lines_still_claim(self):
        from nidra.adapters.memory_files import _extract_paths
        for line in ("the guard lives in /Users/x/projects/app/main.py today",
                     "removed the retry from /Users/x/projects/app/net.py"):
            self.assertEqual(len(_extract_paths(line)), 1,
                             "dropped a real claim: " + line)

    def test_backticked_paths_may_contain_spaces(self):
        from nidra.adapters.memory_files import _extract_paths
        got = _extract_paths("marketplace lives at `~/Documents/travel website/marketplace`")
        self.assertEqual(len(got), 1, got)
        self.assertTrue(got[0][0].endswith("travel website/marketplace"), got[0][0])

    def test_no_duplicate_when_backticked(self):
        """The backtick pass and the bare pass must not both claim one path."""
        from nidra.adapters.memory_files import _extract_paths
        got = _extract_paths("see `/Users/x/projects/app/main.py` for the guard")
        self.assertEqual(len(got), 1, got)


class TestWikilinkTargets(unittest.TestCase):
    """Two ways the wikilink check invented broken links (4 of 16 items).

    [[name.md]] became name.md.md — the file was right there. [[#anchor]] is
    an in-document heading link, not a memory, and became #anchor.md.
    """

    def test_md_suffix_not_doubled(self):
        import tempfile as _tf
        with _tf.TemporaryDirectory() as td:
            open(os.path.join(td, "target-mem.md"), "w").write("x")
            md = os.path.join(td, "src.md")
            open(md, "w").write(
                "---\nname: src\ndescription: d\n---\n"
                "See [[target-mem.md]] for the long story of how it works.\n")
            mem, _ = file_to_memory(md, td)
            wl = [e for e in mem["evidence"] if e["locator"].startswith("wikilink")]
            self.assertEqual(len(wl), 1)
            self.assertTrue(os.path.exists(wl[0]["source"]), wl[0]["source"])

    def test_anchor_links_are_not_memories(self):
        links = _extract_wikilinks("jump to [[#increment-3]] below")
        self.assertEqual(links, [], links)

    def test_plain_link_unchanged(self):
        links = _extract_wikilinks("see [[some-memory]] here")
        self.assertEqual(links[0][0], "some-memory")


class TestQuotedWikilinksAreSyntax(unittest.TestCase):
    """A wikilink inside backticks is QUOTED SYNTAX, not a link.

    Two memories describe the wikilink format itself — "parses index lines
    and `[[wikilinks]]`" — and were marked drifted for not having a memory
    literally named "wikilinks". Same rule the path pass uses, inverted:
    backticks mean "this is code being shown", not "this is a location".
    """

    def test_backticked_link_is_not_a_link(self):
        self.assertEqual(_extract_wikilinks("parses index lines and `[[wikilinks]]` too"), [])
        self.assertEqual(_extract_wikilinks("strip `<poem>/{{tpl}}/[[link]]` markup"), [])

    def test_unbackticked_link_still_counts(self):
        got = _extract_wikilinks("related: [[some-memory]] and `code` here")
        self.assertEqual([g[0] for g in got], ["some-memory"])


class TestReimportReplacesDerivedEvidence(unittest.TestCase):
    """Fixing a memory file must be able to CLEAR its drift.

    Evidence for a memory-file memory is derived from the file. The importer
    unioned it, so a claim that entered the store once could never leave: the
    owner fixed the .md, re-graded, and the queue still showed the old path.
    The correction loop had no exit. Derived rows are now replaced.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.mem_dir = os.path.join(self.tmp, "memory")
        os.makedirs(self.mem_dir)
        self.store = Store(os.path.join(self.tmp, "store"))
        self.store.init()
        self.f = os.path.join(self.mem_dir, "m.md")

    def _write(self, body):
        with open(self.f, "w") as fh:
            fh.write("---\nname: m\ndescription: a memory with a long enough statement\n---\n" + body)

    def test_removing_a_path_from_the_file_removes_the_claim(self):
        self._write("the thing lives at /Users/x/projects/gone/old.py right now\n")
        import_memory_files(self.store, self.mem_dir)
        locs = [e["locator"] for e in self.store.load()[0]["evidence"]]
        self.assertIn("path:/Users/x/projects/gone/old.py", locs)

        self._write("the thing lives at /Users/x/projects/here/new.py right now\n")
        import_memory_files(self.store, self.mem_dir)
        locs = [e["locator"] for e in self.store.load()[0]["evidence"]]
        self.assertNotIn("path:/Users/x/projects/gone/old.py", locs,
                         "stale claim survived a re-import: the repair loop has no exit")
        self.assertIn("path:/Users/x/projects/here/new.py", locs)

    def test_hand_added_evidence_is_preserved(self):
        """Only DERIVED rows are replaced — anything else stays."""
        self._write("the thing lives at /Users/x/projects/here/new.py right now\n")
        import_memory_files(self.store, self.mem_dir)
        mems = self.store.load()
        mems[0]["evidence"].append({"source": "manual", "excerpt": "hand added",
                                    "sha256": "x", "locator": "command:pytest -q",
                                    "checked_at": None})
        self.store.save(mems)
        import_memory_files(self.store, self.mem_dir)
        locs = [e["locator"] for e in self.store.load()[0]["evidence"]]
        self.assertIn("command:pytest -q", locs, "re-import ate non-derived evidence")


if __name__ == "__main__":
    unittest.main()
