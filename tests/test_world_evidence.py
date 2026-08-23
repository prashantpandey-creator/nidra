"""World-decidable evidence: the git commit kind, and the scope split.

WHY. `machine_checked` conflated two different guarantees. Measured on a real
store 2026-08-23: of 483 evidenced memories, **206 (43%) had QUOTE-ONLY
evidence** — their green grade meant "this memory quotes its own source
correctly", which no change in the world can ever falsify. 58% of all evidence
rows were wikilinks: internal graph consistency, not world coupling.

A knowledge base can be perfectly self-consistent and entirely wrong. So the
grade now carries an orthogonal `evidence_scope`:

    world  — at least one row is falsifiable BY THE WORLD (path, wikilink
             target, git commit). Popper-checkable.
    quote  — every row only proves the memory quotes its source (content
             anchors). Consistent, not corroborated.
    none   — no evidence at all.

And a new world-decidable kind: `git:<repo>@<sha>`. Chosen over commands and
URLs on measurement + risk: 419 SHA citations across 38% of memory files, and
verification is a fixed-argv `git cat-file` — no shell, no network, no
execution of anything a memory file names. Running `command:` evidence from
agent-written memory files on an unattended hourly heartbeat is a code
execution vector; that kind is deliberately NOT implemented.

The three-valued rule applies here too and is the subtle part: a SHA that is
absent from the repos we know about is NOT proof the commit is gone — it may
be the wrong repo list. Only a claim naming a definite repo can be falsified.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nidra.grade import evidence_scope, grade, verify_evidence_row
from nidra.store import new_memory, sha256_text


def _row(locator, source="", excerpt="x"):
    return {"source": source, "excerpt": excerpt, "sha256": sha256_text(excerpt),
            "locator": locator, "checked_at": None}


def _git_repo(d):
    """A real repo with one real commit. Returns (path, sha)."""
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    subprocess.run(["git", "init", "-q", d], check=True, env=env)
    open(os.path.join(d, "f.txt"), "w").write("hello")
    subprocess.run(["git", "-C", d, "add", "f.txt"], check=True, env=env)
    subprocess.run(["git", "-C", d, "commit", "-qm", "first"], check=True, env=env)
    sha = subprocess.run(["git", "-C", d, "rev-parse", "HEAD"],
                         capture_output=True, text=True, check=True).stdout.strip()
    return d, sha


class TestGitEvidence(unittest.TestCase):
    def test_real_commit_verifies(self):
        with tempfile.TemporaryDirectory() as d:
            repo, sha = _git_repo(d)
            state, _ = verify_evidence_row(_row("git:%s@%s" % (repo, sha)))
            self.assertEqual(state, "ok")

    def test_short_sha_verifies(self):
        with tempfile.TemporaryDirectory() as d:
            repo, sha = _git_repo(d)
            state, _ = verify_evidence_row(_row("git:%s@%s" % (repo, sha[:7])))
            self.assertEqual(state, "ok")

    def test_git_evidence_is_CONFIRM_ONLY(self):
        """A commit absent from the repos we guessed is NOT drift.

        Measured on the live store: of 24 git claims the first version called
        "drifted", 14 (58%) were real commits sitting in a repo the memory
        did not name. The repo for a bare SHA is inferred, so the claim is
        semi-decidable: finding it proves presence; not finding it proves
        only that we looked in the wrong places. One-sided by construction —
        it raises confidence, it never manufactures work.
        """
        with tempfile.TemporaryDirectory() as d:
            repo, _ = _git_repo(d)
            state, reason = verify_evidence_row(
                _row("git:%s@%s" % (repo, "0" * 40)))
            self.assertEqual(state, "source_missing", reason)
            self.assertNotEqual(state, "drifted")

    def test_missing_repo_is_not_checkable_not_drift(self):
        """THE falsifier. A repo we cannot see is 'I don't know', never
        'the commit is gone' — the same three-valued rule that the extractor
        violated 28 times."""
        with tempfile.TemporaryDirectory() as d:
            state, reason = verify_evidence_row(
                _row("git:%s/no-such-repo@%s" % (d, "a" * 40)))
            self.assertEqual(state, "source_missing", reason)

    def test_a_file_that_is_not_a_repo_is_not_checkable(self):
        with tempfile.TemporaryDirectory() as d:
            state, _ = verify_evidence_row(_row("git:%s@%s" % (d, "a" * 40)))
            self.assertEqual(state, "source_missing")

    def test_locator_is_not_shell_interpreted(self):
        """A memory file is written by agents. It must never be able to run
        anything: verification is fixed-argv git, so shell metacharacters in
        a SHA are inert, not executed."""
        with tempfile.TemporaryDirectory() as d:
            repo, _ = _git_repo(d)
            canary = os.path.join(d, "pwned")
            state, _ = verify_evidence_row(
                _row("git:%s@%s" % (repo, "abc; touch %s" % canary)))
            self.assertFalse(os.path.exists(canary), "locator reached a shell")
            self.assertEqual(state, "source_missing")


class TestEvidenceScope(unittest.TestCase):
    def test_quote_only_memory_is_scope_quote(self):
        m = new_memory("a statement")
        m["evidence"] = [_row("content_anchor", source="/tmp/x", excerpt="hello")]
        self.assertEqual(evidence_scope(m), "quote")

    def test_path_claim_makes_it_world(self):
        m = new_memory("a statement")
        m["evidence"] = [_row("content_anchor", excerpt="hello"),
                         _row("path:/tmp")]
        self.assertEqual(evidence_scope(m), "world")

    def test_git_claim_makes_it_world(self):
        m = new_memory("a statement")
        m["evidence"] = [_row("git:/tmp/r@abc1234")]
        self.assertEqual(evidence_scope(m), "world")

    def test_no_evidence_is_none(self):
        m = new_memory("a statement")
        m["evidence"] = []
        self.assertEqual(evidence_scope(m), "none")

    def test_scope_is_orthogonal_to_grade(self):
        """A quote-only memory can still be machine_checked — that is exactly
        the conflation being surfaced, not a bug. The point is that the two
        facts are now separately readable."""
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "m.md")
            open(src, "w").write("the anchor line lives here\n")
            m = new_memory("s")
            m["evidence"] = [_row("content_anchor", source=src,
                                  excerpt="the anchor line lives here")]
            status, _, _ = grade(m)
            self.assertEqual(status, "machine_checked")
            self.assertEqual(evidence_scope(m), "quote")


class TestGitClaimExtraction(unittest.TestCase):
    """A SHA is only a CLAIM when the memory pins down which repo it is in.

    Absent from the repos we happen to know is not proof the commit is gone —
    it may be the wrong repo list. So the extractor emits a git claim only
    when the same memory file names a path that resolves to a real repo.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo, self.sha = _git_repo(os.path.join(self.tmp, "repo"))

    def _claims(self, body):
        from nidra.adapters.memory_files import _extract_git_claims
        return [c for c, _ in _extract_git_claims(body)]

    def test_sha_plus_repo_path_in_the_same_file(self):
        got = self._claims("Fixed in `%s` — see %s/f.txt for the guard."
                           % (self.sha[:7], self.repo))
        self.assertEqual(got, ["git:%s@%s" % (self.repo, self.sha[:7])], got)

    def test_sha_with_no_repo_named_is_not_a_claim(self):
        self.assertEqual(self._claims("Fixed in `%s`, shipped." % self.sha[:7]), [])

    def test_hex_that_is_not_a_sha_is_not_a_claim(self):
        # NOTE: "deadbee" is NOT here — it is 7 lowercase hex chars, exactly
        # the shape of a real short sha. Nothing lexical separates a
        # placeholder from a citation; git decides, and says "no such commit".
        for word in ("`123456789`", "`#ff9933`", "`abc`", "`ABCDEF1`"):
            self.assertEqual(
                self._claims("colour %s at %s/f.txt" % (word, self.repo)), [],
                "claimed a non-sha: " + word)

    def test_path_inside_the_repo_resolves_to_the_repo_root(self):
        deep = os.path.join(self.repo, "f.txt")
        got = self._claims("see `%s` — landed in `%s`" % (deep, self.sha[:8]))
        self.assertEqual(got, ["git:%s@%s" % (self.repo, self.sha[:8])], got)


class TestMultiRepoGitClaims(unittest.TestCase):
    """A memory naming several repos must not have its commits pinned to the
    first one.

    Measured 2026-08-23, immediately after shipping the single-repo version:
    31 git claims failed, and every sampled one was a REAL commit sitting in a
    different repo the same memory named. Guessing repos[0] and then reporting
    a definite "drifted" is the instrument error this whole layer exists to
    prevent — reintroduced by me, caught by the live store.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.r1, self.s1 = _git_repo(os.path.join(self.tmp, "one"))
        self.r2, self.s2 = _git_repo(os.path.join(self.tmp, "two"))

    def test_commit_in_the_SECOND_named_repo_still_verifies(self):
        from nidra.adapters.memory_files import _extract_git_claims
        body = "Work spans %s and %s — the fix landed in `%s`." % (
            self.r1, self.r2, self.s2[:7])
        claims = [c for c, _ in _extract_git_claims(body)]
        self.assertEqual(len(claims), 1, claims)
        state, why = verify_evidence_row(_row(claims[0]))
        self.assertEqual(state, "ok", why)

    def test_absent_from_every_named_repo_is_still_not_drift(self):
        state, _ = verify_evidence_row(
            _row("git:%s|%s@%s" % (self.r1, self.r2, "0" * 40)))
        self.assertEqual(state, "source_missing")

    def test_unreadable_repos_stay_not_checkable(self):
        state, _ = verify_evidence_row(
            _row("git:%s/nope|%s/also-nope@%s" % (self.tmp, self.tmp, "a" * 40)))
        self.assertEqual(state, "source_missing")

    def test_a_git_claim_never_reaches_the_repair_queue(self):
        """The property that matters: no git verdict can create work."""
        for loc in ("git:%s@%s" % (self.r1, "0" * 40),
                    "git:%s|%s@%s" % (self.r1, self.r2, "0" * 40),
                    "git:%s/nope@%s" % (self.tmp, "a" * 40)):
            self.assertNotEqual(verify_evidence_row(_row(loc))[0], "drifted", loc)


if __name__ == "__main__":
    unittest.main()
