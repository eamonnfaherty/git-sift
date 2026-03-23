"""Persistent review session — saves decisions between wizard runs."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Optional

from git_sift.models import DiffOptions, FileReview, ReviewDecision


# ── Session file location ────────────────────────────────────────────────────

def _git_dir() -> Optional[Path]:
    """Return the .git directory for the current repo, or None."""
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def session_path() -> Optional[Path]:
    """Return the path to the session file, or None if not in a git repo."""
    git_dir = _git_dir()
    if git_dir is None:
        return None
    return git_dir / "git-sift-session.json"


# ── Hashing ──────────────────────────────────────────────────────────────────

def diff_hash(raw_diff: str) -> str:
    """Return a short SHA-256 hex digest of a raw diff string."""
    return hashlib.sha256(raw_diff.encode()).hexdigest()[:16]


# ── Options key ──────────────────────────────────────────────────────────────

def _options_key(options: DiffOptions) -> dict:
    return {
        "mode": options.mode.value,
        "ref_a": options.ref_a,
        "ref_b": options.ref_b,
    }


# ── Load / save ──────────────────────────────────────────────────────────────

def load_session(options: DiffOptions) -> dict[str, dict]:
    """
    Load saved file decisions for the given options.

    Returns a dict mapping file display_path → {diff_hash, decision, note}.
    Returns an empty dict if no session exists or the options don't match.
    """
    path = session_path()
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if data.get("options") != _options_key(options):
        return {}
    return data.get("files", {})


def save_session(options: DiffOptions, reviews: list[FileReview]) -> None:
    """Persist the current review decisions to the session file."""
    path = session_path()
    if path is None:
        return
    files: dict[str, dict] = {}
    for r in reviews:
        if r.decision is not None:
            files[r.diff_file.display_path] = {
                "diff_hash": diff_hash(r.diff_file.raw_diff),
                "decision": r.decision.value,
                "note": r.note,
            }
    data = {
        "version": 1,
        "options": _options_key(options),
        "files": files,
    }
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


def clear_session() -> None:
    """Delete the session file."""
    path = session_path()
    if path and path.exists():
        path.unlink(missing_ok=True)


# ── Apply saved decisions to a fresh list of FileReview objects ──────────────

class RestoreResult:
    def __init__(self) -> None:
        self.carried: list[FileReview] = []   # decision unchanged, restored
        self.changed: list[FileReview] = []   # previously reviewed, diff changed
        self.fresh: list[FileReview] = []     # never reviewed before

    @property
    def total_carried(self) -> int:
        return len(self.carried)


def restore_decisions(
    reviews: list[FileReview],
    saved: dict[str, dict],
) -> RestoreResult:
    """
    Apply previously saved decisions to a fresh list of reviews.

    - carried: diff unchanged → decision restored, no prompt needed
    - changed: diff changed since last review → must re-review
    - fresh:   not in session at all → prompt as normal
    """
    result = RestoreResult()
    for review in reviews:
        key = review.diff_file.display_path
        if key not in saved:
            result.fresh.append(review)
            continue

        entry = saved[key]
        current_hash = diff_hash(review.diff_file.raw_diff)

        if entry["diff_hash"] == current_hash:
            # Restore decision — no need to re-prompt
            review.decision = ReviewDecision(entry["decision"])
            review.note = entry.get("note")
            result.carried.append(review)
        else:
            # Diff has changed — needs fresh review
            result.changed.append(review)

    return result
