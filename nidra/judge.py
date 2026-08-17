"""nidra.judge — the optional LLM stage, for what determinism cannot settle.

Nidra's core never needs an API key: dedup, verification, drift demotion,
scheduling, and pruning are deterministic. Only genuinely *contested* pairs
(two memories, same subject, conflicting claims) benefit from judgment, and
that judgment is pluggable: anything with a ``resolve(a, b) -> dict`` method.

The bundled ``AnthropicJudge`` defaults to ``claude-haiku-4-5`` because
contested-pair arbitration is a bulk, low-stakes classification task — pass a
bigger model for higher-stakes stores. It fails open: any error returns "no
winner" and the pair simply stays flagged for a human.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class NullJudge:
    def resolve(self, a: Dict[str, Any], b: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None


def _contest_prompt(a: Dict[str, Any], b: Dict[str, Any]) -> str:
    return (
        "Two stored memories about the same subject contradict each other.\n"
        "Memory A: %r (evidence rows: %d, grade: %s)\n"
        "Memory B: %r (evidence rows: %d, grade: %s)\n"
        "Reply with exactly one line: 'A', 'B', or 'NEITHER', then a colon "
        "and a one-sentence reason. Prefer the memory with verified evidence; "
        "if neither has evidence, reply NEITHER."
        % (
            a["statement"],
            len(a["evidence"]),
            a["epistemic"]["evidence_status"],
            b["statement"],
            len(b["evidence"]),
            b["epistemic"]["evidence_status"],
        )
    )


def _parse_verdict(text: str) -> Dict[str, Any]:
    head, _, reason = text.strip().partition(":")
    head = head.strip().upper()
    if head == "A":
        return {"winner": "a", "reason": reason.strip()}
    if head == "B":
        return {"winner": "b", "reason": reason.strip()}
    return {"winner": None, "reason": reason.strip() or text.strip()}


class ClaudeCLIJudge:
    """The default judge: Claude Code's own CLI. No API key, ever."""

    def __init__(self, model: Optional[str] = "haiku", ask=None):
        from .claude_cli import ask_claude

        self.model = model
        self._ask = ask or ask_claude

    def resolve(self, a: Dict[str, Any], b: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            return _parse_verdict(self._ask(_contest_prompt(a, b), model=self.model))
        except Exception as exc:  # fail open — contested beats wrongly judged
            return {"winner": None, "reason": "judge unavailable: %s" % exc}


def auto_judge(model: Optional[str] = "haiku"):
    """Best available judge: Claude Code CLI first, SDK only as explicit fallback."""
    from .claude_cli import claude_available

    if claude_available():
        return ClaudeCLIJudge(model=model)
    try:
        import anthropic  # noqa: F401

        return AnthropicJudge()
    except Exception:
        return NullJudge()


class AnthropicJudge:
    def __init__(self, model: str = "claude-haiku-4-5", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic  # imported lazily; nidra core has no dependencies

            self._client = (
                anthropic.Anthropic(api_key=self.api_key) if self.api_key else anthropic.Anthropic()
            )
        return self._client

    def resolve(self, a: Dict[str, Any], b: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            response = self._get_client().messages.create(
                model=self.model,
                max_tokens=200,
                messages=[{"role": "user", "content": _contest_prompt(a, b)}],
            )
            text = next(
                (block.text for block in response.content if block.type == "text"), ""
            ).strip()
        except Exception as exc:  # fail open — contested beats wrongly judged
            return {"winner": None, "reason": "judge unavailable: %s" % exc}
        return _parse_verdict(text)
