"""Tests for review session persistence."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from git_sift.models import DiffFile, DiffHunk, DiffMode, DiffOptions, FileReview, FlagReason, ReviewDecision, RiskCategory
from git_sift.session import (
    clear_session,
    diff_hash,
    load_session,
    restore_decisions,
    save_session,
    session_path,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_options(mode=DiffMode.STAGED, ref_a=None, ref_b=None) -> DiffOptions:
    return DiffOptions(mode=mode, ref_a=ref_a, ref_b=ref_b)


def _make_review(path: str, raw_diff: str = "@@ -1 +1 @@\n-old\n+new\n") -> FileReview:
    diff_file = DiffFile(old_path=path, new_path=path, raw_diff=raw_diff)
    return FileReview(diff_file=diff_file, category=RiskCategory.EXISTING_CODE)


def _fake_session_path(tmp_path: Path) -> Path:
    return tmp_path / ".git" / "git-sift-session.json"


# ── diff_hash ─────────────────────────────────────────────────────────────────

def test_diff_hash_is_deterministic():
    assert diff_hash("hello") == diff_hash("hello")


def test_diff_hash_differs_for_different_content():
    assert diff_hash("foo") != diff_hash("bar")


def test_diff_hash_is_16_chars():
    assert len(diff_hash("anything")) == 16


# ── load_session ─────────────────────────────────────────────────────────────

def test_load_session_returns_empty_when_no_file(tmp_path):
    dest = _fake_session_path(tmp_path)
    with patch("git_sift.session.session_path", return_value=dest):
        assert load_session(_make_options()) == {}


def test_load_session_returns_empty_when_options_mismatch(tmp_path):
    dest = _fake_session_path(tmp_path)
    dest.parent.mkdir(parents=True)
    data = {"version": 1, "options": {"mode": "refs", "ref_a": "main", "ref_b": "HEAD"}, "files": {}}
    dest.write_text(json.dumps(data))
    with patch("git_sift.session.session_path", return_value=dest):
        assert load_session(_make_options(mode=DiffMode.STAGED)) == {}


def test_load_session_returns_files_when_options_match(tmp_path):
    dest = _fake_session_path(tmp_path)
    dest.parent.mkdir(parents=True)
    options = _make_options()
    data = {
        "version": 1,
        "options": {"mode": "staged", "ref_a": None, "ref_b": None},
        "files": {"src/app.py": {"diff_hash": "abc123", "decision": "approve", "note": None}},
    }
    dest.write_text(json.dumps(data))
    with patch("git_sift.session.session_path", return_value=dest):
        result = load_session(options)
    assert "src/app.py" in result
    assert result["src/app.py"]["decision"] == "approve"


def test_load_session_returns_empty_on_corrupt_file(tmp_path):
    dest = _fake_session_path(tmp_path)
    dest.parent.mkdir(parents=True)
    dest.write_text("not json")
    with patch("git_sift.session.session_path", return_value=dest):
        assert load_session(_make_options()) == {}


# ── save_session ──────────────────────────────────────────────────────────────

def test_save_session_writes_file(tmp_path):
    dest = _fake_session_path(tmp_path)
    dest.parent.mkdir(parents=True)
    options = _make_options()
    review = _make_review("src/app.py", raw_diff="@@ -1 +1 @@\n-a\n+b\n")
    review.decision = ReviewDecision.APPROVE
    with patch("git_sift.session.session_path", return_value=dest):
        save_session(options, [review])
    data = json.loads(dest.read_text())
    assert "src/app.py" in data["files"]
    assert data["files"]["src/app.py"]["decision"] == "approve"


def test_save_session_skips_undecided_files(tmp_path):
    dest = _fake_session_path(tmp_path)
    dest.parent.mkdir(parents=True)
    options = _make_options()
    review = _make_review("src/app.py")  # no decision set
    with patch("git_sift.session.session_path", return_value=dest):
        save_session(options, [review])
    data = json.loads(dest.read_text())
    assert data["files"] == {}


# ── clear_session ─────────────────────────────────────────────────────────────

def test_clear_session_deletes_file(tmp_path):
    dest = _fake_session_path(tmp_path)
    dest.parent.mkdir(parents=True)
    dest.write_text("{}")
    with patch("git_sift.session.session_path", return_value=dest):
        clear_session()
    assert not dest.exists()


def test_clear_session_is_safe_when_no_file(tmp_path):
    dest = _fake_session_path(tmp_path)
    with patch("git_sift.session.session_path", return_value=dest):
        clear_session()  # should not raise


# ── restore_decisions ─────────────────────────────────────────────────────────

def test_restore_carried_when_diff_unchanged():
    raw = "@@ -1 +1 @@\n-old\n+new\n"
    review = _make_review("src/app.py", raw_diff=raw)
    saved = {"src/app.py": {"diff_hash": diff_hash(raw), "decision": "approve", "note": None}}
    result = restore_decisions([review], saved)
    assert len(result.carried) == 1
    assert len(result.changed) == 0
    assert len(result.fresh) == 0
    assert review.decision == ReviewDecision.APPROVE


def test_restore_changed_when_diff_differs():
    review = _make_review("src/app.py", raw_diff="@@ -1 +1 @@\n-old\n+new\n")
    saved = {"src/app.py": {"diff_hash": "differenthash1234", "decision": "approve", "note": None}}
    result = restore_decisions([review], saved)
    assert len(result.changed) == 1
    assert review.decision is None  # NOT restored — needs fresh review


def test_restore_fresh_when_not_in_session():
    review = _make_review("src/newfile.py")
    result = restore_decisions([review], {})
    assert len(result.fresh) == 1
    assert review.decision is None


def test_restore_mixed():
    raw_same = "@@ -1 +1 @@\n-x\n+y\n"
    raw_changed = "@@ -1 +1 @@\n-a\n+b\n"
    r_carried = _make_review("same.py", raw_diff=raw_same)
    r_changed = _make_review("changed.py", raw_diff=raw_changed)
    r_fresh = _make_review("new.py")
    saved = {
        "same.py": {"diff_hash": diff_hash(raw_same), "decision": "approve", "note": None},
        "changed.py": {"diff_hash": "oldhashxxxxxxxx", "decision": "blocker", "note": "fix it"},
    }
    result = restore_decisions([r_carried, r_changed, r_fresh], saved)
    assert result.total_carried == 1
    assert len(result.changed) == 1
    assert len(result.fresh) == 1
    assert r_carried.decision == ReviewDecision.APPROVE
    assert r_changed.decision is None   # must be re-reviewed
