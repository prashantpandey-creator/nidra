"""Precision/recall of the claim extractor, measured against a fixed corpus.

WHY THIS EXISTS. nidra turns its own findings into work: a failing claim
becomes a repair-queue item, and a repair-queue item can become a dispatched
agent. So an extractor that over-claims does not produce a wrong number — it
produces *invented work*, and whoever installed the tool pays for it in tokens
before anyone notices.

Measured on one real store 2026-08-23: **28 of 30** memories "failing
verification" had not drifted at all. The extractor was asserting that
`<project-slug>`, `foo-*.tar.gz`, `file.py:45` and paths a memory explicitly
says are *gone* should exist on disk. An agent dispatched to repair them burned
~44k tokens and changed nothing.

That was caught by a person looking. This file is so the next one is caught by
CI instead — against a corpus that ships with the tool, not against whichever
real memories a user happens to have.

ADDING A CASE: drop a .md in tests/fixtures/memory_corpus/ and add its exact
expected claims to expected.json. Over-claiming fails on precision;
under-claiming fails on recall. Both are failures — a checker that refuses
everything is not "safe", it is blind.
"""
from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nidra.adapters.memory_files import (
    _extract_paths,
    _extract_wikilinks,
    _parse_frontmatter,
)

CORPUS = os.path.join(os.path.dirname(__file__), "fixtures", "memory_corpus")


def _load():
    with open(os.path.join(CORPUS, "expected.json"), encoding="utf-8") as fh:
        return json.load(fh)


def _claims(fname):
    with open(os.path.join(CORPUS, fname), encoding="utf-8") as fh:
        _, body = _parse_frontmatter(fh.read())
    paths = [p for p, _ in _extract_paths(body)]
    links = [t for t, _ in _extract_wikilinks(body)]
    return paths, links


def _norm(p):
    """Expected paths are written with ~ for readability; the extractor expands."""
    return os.path.expanduser(p)


class TestExtractorCorpus(unittest.TestCase):
    def test_every_fixture_has_an_expectation(self):
        expected = _load()
        onfile = {f for f in os.listdir(CORPUS) if f.endswith(".md")}
        self.assertEqual(onfile, set(expected),
                         "a fixture with no expectation is untested: %s"
                         % sorted(onfile ^ set(expected)))

    def test_exact_claims_per_fixture(self):
        for fname, want in sorted(_load().items()):
            with self.subTest(fixture=fname):
                got_p, got_w = _claims(fname)
                self.assertEqual(sorted(got_p), sorted(_norm(p) for p in want["paths"]),
                                 "path claims wrong in %s" % fname)
                self.assertEqual(sorted(got_w), sorted(want["wikilinks"]),
                                 "wikilink claims wrong in %s" % fname)

    def test_precision_and_recall_are_perfect_on_the_corpus(self):
        """One number, so a regression is visible as a number.

        Precision below 1.0 means the tool would invent work. Recall below 1.0
        means it would miss real drift and quietly serve a stale memory.
        """
        tp = fp = fn = 0
        for fname, want in _load().items():
            got_p, got_w = _claims(fname)
            got = set(got_p) | {"[[%s]]" % t for t in got_w}
            exp = {_norm(p) for p in want["paths"]} | {"[[%s]]" % t for t in want["wikilinks"]}
            tp += len(got & exp)
            fp += len(got - exp)
            fn += len(exp - got)
        precision = tp / (tp + fp) if (tp + fp) else 1.0
        recall = tp / (tp + fn) if (tp + fn) else 1.0
        self.assertEqual(fp, 0, "extractor invents %d claim(s) — precision %.2f" % (fp, precision))
        self.assertEqual(fn, 0, "extractor misses %d real claim(s) — recall %.2f" % (fn, recall))

    def test_the_corpus_actually_covers_the_known_traps(self):
        """A corpus that drifts out of coverage is worse than none — it reads
        as protection while protecting nothing."""
        blob = ""
        for f in os.listdir(CORPUS):
            if f.endswith(".md"):
                with open(os.path.join(CORPUS, f), encoding="utf-8") as fh:
                    blob += fh.read()
        for trap, token in [
            ("angle-bracket template", "<project-slug>"),
            ("glob", "-*.tar.gz"),
            ("brace expansion", "{iOS,macOS}"),
            ("date placeholder", "YYYYMMDD"),
            ("line reference", ".py:45"),
            ("absence statement", "is gone"),
            ("path containing a space", "side projects/"),
            ("wikilink with .md suffix", "[[retry-policy.md]]"),
            ("in-document anchor", "[[#section-three]]"),
            ("GAP placeholder", "[[GAP]]"),
            ("backticked wikilink syntax", "`[[wikilinks]]`"),
            ("aliased wikilink", "|the runbook]]"),
        ]:
            self.assertIn(token, blob, "corpus lost coverage of: %s" % trap)


if __name__ == "__main__":
    unittest.main()
