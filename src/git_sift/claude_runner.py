"""Utilities for launching an interactive Claude Code session."""
from __future__ import annotations

import shutil
import subprocess


def check_claude_available() -> bool:
    """Return True if the `claude` CLI is found on PATH."""
    return shutil.which("claude") is not None


def run_claude(prompt: str) -> bool:
    """
    Launch an interactive Claude Code session in the current terminal.

    The session runs with the given prompt as the initial message.
    Returns True when the user exits (all exit codes treated as "done").
    """
    subprocess.run(["claude", prompt])
    return True
