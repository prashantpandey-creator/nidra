"""Nidra — the sleep cycle for AI memory.

Every memory carries its evidence; a scheduled pass keeps the evidence honest.
"""
from .grade import grade, verify_evidence_row
from .judge import AnthropicJudge, NullJudge
from .report import render_markdown
from .sleep import census, contradicts, run_sleep
from .store import Store, new_memory

__version__ = "0.1.0"

__all__ = [
    "Store",
    "new_memory",
    "grade",
    "verify_evidence_row",
    "run_sleep",
    "census",
    "contradicts",
    "render_markdown",
    "AnthropicJudge",
    "NullJudge",
    "__version__",
]
