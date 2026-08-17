"""The Claude Code bridge: no API key, injectable, fail-open everywhere."""
import os
import subprocess

from nidra.claude_cli import ask_claude
from nidra.eval.longmemeval import _pack_answer_prompt, _parse_tagged, run_qa
from nidra.judge import ClaudeCLIJudge, NullJudge, auto_judge
from nidra.store import new_memory

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "longmemeval_mini.json")


def _completed(stdout="", returncode=0, stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_ask_claude_success_and_model_flag():
    seen = {}

    def runner(cmd, **kw):
        seen["cmd"] = cmd
        return _completed(stdout="OK\n")

    assert ask_claude("hi", model="haiku", runner=runner) == "OK"
    assert seen["cmd"][:2] == ["claude", "-p"] and "--model" in seen["cmd"]


def test_ask_claude_raises_on_not_logged_in_and_failure():
    for proc in (_completed(stdout="Not logged in · Please run /login"),
                 _completed(returncode=1, stderr="boom"),
                 _completed(stdout="")):
        try:
            ask_claude("hi", runner=lambda cmd, **kw: proc)
            assert False, "should have raised"
        except RuntimeError:
            pass


def test_cli_judge_parses_and_fails_open():
    a = new_memory("The port is 80", subject="port")
    b = new_memory("The port is 8080", subject="port")
    judge = ClaudeCLIJudge(ask=lambda p, model=None: "B: b has fresher evidence")
    assert judge.resolve(a, b) == {"winner": "b", "reason": "b has fresher evidence"}

    def broken(prompt, model=None):
        raise RuntimeError("cli gone")

    verdict = ClaudeCLIJudge(ask=broken).resolve(a, b)
    assert verdict["winner"] is None and "cli gone" in verdict["reason"]


def test_auto_judge_prefers_cli(monkeypatch):
    import nidra.judge as judge_mod

    monkeypatch.setattr("nidra.claude_cli.claude_available", lambda: True)
    assert isinstance(judge_mod.auto_judge(), ClaudeCLIJudge)


def test_parse_tagged():
    text = "noise\nA1: Tallinn\n A3:  No information available \nJ9: CORRECT"
    assert _parse_tagged(text, "A") == {1: "Tallinn", 3: "No information available"}
    assert _parse_tagged(text, "J") == {9: "CORRECT"}


def test_run_qa_plumbing_with_fake_bridge(tmp_path):
    """End-to-end QA over the mini fixture with a deterministic fake Claude."""

    def fake_ask(prompt, model=None):
        if prompt.startswith("You answer questions"):
            tag, reply = "A", "an answer from context"
        else:
            tag, reply = "J", "CORRECT"
        import re
        ids = sorted(set(int(x) for x in re.findall(r"### Item (\d+)", prompt)))
        return "\n".join("%s%d: %s" % (tag, i, reply) for i in ids)

    result = run_qa(FIXTURE, str(tmp_path / "work"), ask=fake_ask, batch=2, workers=2)
    assert result["stage"] == "qa" and result["bridge"] == "claude-code-cli"
    assert result["questions_scored"] == 5          # abstention INCLUDED in QA
    assert result["accuracy"] == 1.0
    assert result["abstention"] == {"n": 1, "accuracy": 1.0}
    assert result["unparsed"] == 0

    # a bridge that dies mid-run leaves unparsed items, never fabricated ones
    def dead_ask(prompt, model=None):
        raise RuntimeError("no login")

    result = run_qa(FIXTURE, str(tmp_path / "work2"), ask=dead_ask, batch=2, workers=2)
    assert result["accuracy"] == 0.0 and result["unparsed"] == 5
