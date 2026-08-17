"""nidra.claude_cli — judgment through Claude Code, no API key.

Nidra's core is deterministic and needs no model. When a model *is* wanted
(contested-pair judgment, benchmark QA), the default bridge is the ``claude``
CLI in ``-p``/print mode: it resolves its own authentication (a Claude Code
login), so users who already run Claude Code get judgment with **zero keys,
zero SDKs, zero configuration**. The Anthropic SDK path remains available as
an explicit opt-in for servers that hold an API key.

Everything here fails open: an unavailable or errored CLI returns an error
string upward, and callers leave items flagged for a human rather than guessed.
"""
from __future__ import annotations

import shutil
import subprocess
from typing import Callable, List, Optional

Runner = Callable[..., "subprocess.CompletedProcess"]


def claude_available() -> bool:
    return shutil.which("claude") is not None


def ask_claude(
    prompt: str,
    model: Optional[str] = "haiku",
    timeout: int = 240,
    runner: Runner = subprocess.run,
) -> str:
    """One headless Claude Code call. Raises RuntimeError on any failure."""
    cmd: List[str] = ["claude", "-p", prompt, "--output-format", "text"]
    if model:
        cmd += ["--model", model]
    try:
        result = runner(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise RuntimeError("claude CLI not found — install Claude Code or use the SDK judge")
    except subprocess.TimeoutExpired:
        raise RuntimeError("claude CLI timed out after %ss" % timeout)
    output = (result.stdout or "").strip()
    if result.returncode != 0 or not output or "Not logged in" in output:
        raise RuntimeError(
            "claude CLI unavailable: %s"
            % ((result.stderr or output or "no output").strip()[:200])
        )
    return output
