"""Git integration — runs git diff and returns raw unified diff text."""
from __future__ import annotations

import subprocess
import sys
from typing import Optional

from git_sift.models import DiffMode, DiffOptions

_BASE_FLAGS = ["--no-color", "--unified=3", "--diff-algorithm=histogram"]


def _run_git(args: list[str]) -> str:
    """Run a git command and return stdout. Exit with code 2 on failure."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print("Error: git executable not found. Please install git.", file=sys.stderr)
        sys.exit(2)

    if result.returncode != 0:
        print(f"Error running git:\n{result.stderr.strip()}", file=sys.stderr)
        sys.exit(2)

    return result.stdout


def get_current_branch() -> Optional[str]:
    """Return the current branch name, or None if in detached HEAD state."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            return None if branch == "HEAD" else branch
    except FileNotFoundError:
        pass
    return None


def get_default_base() -> str:
    """Return the best default base branch: 'main' if it exists, else 'master'."""
    result = subprocess.run(
        ["git", "branch", "--list", "main"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return "main"
    result2 = subprocess.run(
        ["git", "branch", "--list", "master"],
        capture_output=True,
        text=True,
    )
    if result2.returncode == 0 and result2.stdout.strip():
        return "master"
    return "main"


def fetch_diff(options: DiffOptions) -> str:
    """Run the appropriate git diff command and return the raw diff text."""
    if options.mode == DiffMode.STAGED:
        return _run_git(["diff", "--cached"] + _BASE_FLAGS)
    elif options.mode == DiffMode.UNSTAGED:
        return _run_git(["diff"] + _BASE_FLAGS)
    elif options.mode == DiffMode.REFS:
        ref_a = options.ref_a or get_default_base()
        ref_b = options.ref_b or "HEAD"
        return _run_git(["diff", f"{ref_a}...{ref_b}"] + _BASE_FLAGS)
    else:
        raise ValueError(f"Unknown DiffMode: {options.mode}")


def assert_in_git_repo() -> None:
    """Exit with code 2 if the current directory is not inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print("Error: git executable not found.", file=sys.stderr)
        sys.exit(2)

    if result.returncode != 0:
        print("Error: not inside a git repository.", file=sys.stderr)
        sys.exit(2)
