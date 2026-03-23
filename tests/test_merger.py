"""Tests for working-tree-clean and PR-exists checks."""
from unittest.mock import MagicMock, patch

import pytest

from git_sift.merger import check_pr_exists, check_working_tree_clean, prompt_and_merge


# ---------------------------------------------------------------------------
# check_working_tree_clean
# ---------------------------------------------------------------------------

class TestCheckWorkingTreeClean:
    def test_returns_true_when_no_changes(self):
        mock_result = MagicMock(returncode=0, stdout="")
        with patch("git_sift.merger.subprocess.run", return_value=mock_result):
            assert check_working_tree_clean() is True

    def test_returns_false_when_unstaged_changes(self):
        mock_result = MagicMock(returncode=0, stdout=" M src/app.py\n")
        with patch("git_sift.merger.subprocess.run", return_value=mock_result):
            assert check_working_tree_clean() is False

    def test_returns_false_when_git_fails(self):
        mock_result = MagicMock(returncode=128, stdout="")
        with patch("git_sift.merger.subprocess.run", return_value=mock_result):
            assert check_working_tree_clean() is False


# ---------------------------------------------------------------------------
# check_pr_exists
# ---------------------------------------------------------------------------

class TestCheckPrExists:
    def test_returns_none_when_gh_not_installed(self):
        with patch("git_sift.merger.shutil.which", return_value=None):
            assert check_pr_exists() is None

    def test_returns_none_when_command_fails(self):
        with (
            patch("git_sift.merger.shutil.which", return_value="/usr/bin/gh"),
            patch(
                "git_sift.merger.subprocess.run",
                return_value=MagicMock(returncode=1, stdout=""),
            ),
        ):
            assert check_pr_exists() is None

    def test_returns_none_when_no_open_pr(self):
        import json
        payload = json.dumps({"number": 42, "state": "MERGED", "headRefName": "feat/x", "url": "https://example.com"})
        with (
            patch("git_sift.merger.shutil.which", return_value="/usr/bin/gh"),
            patch(
                "git_sift.merger.subprocess.run",
                return_value=MagicMock(returncode=0, stdout=payload),
            ),
        ):
            assert check_pr_exists() is None

    def test_returns_pr_data_when_open(self):
        import json
        payload = json.dumps({"number": 7, "state": "OPEN", "headRefName": "feat/y", "url": "https://example.com/7"})
        with (
            patch("git_sift.merger.shutil.which", return_value="/usr/bin/gh"),
            patch(
                "git_sift.merger.subprocess.run",
                return_value=MagicMock(returncode=0, stdout=payload),
            ),
        ):
            result = check_pr_exists()
        assert result is not None
        assert result["number"] == 7
        assert result["url"] == "https://example.com/7"

    def test_returns_none_on_invalid_json(self):
        with (
            patch("git_sift.merger.shutil.which", return_value="/usr/bin/gh"),
            patch(
                "git_sift.merger.subprocess.run",
                return_value=MagicMock(returncode=0, stdout="not json"),
            ),
        ):
            assert check_pr_exists() is None


# ---------------------------------------------------------------------------
# prompt_and_merge
# ---------------------------------------------------------------------------

class TestPromptAndMerge:
    def _open_pr(self):
        return {
            "number": 5,
            "state": "OPEN",
            "headRefName": "feat/z",
            "url": "https://example.com/5",
        }

    def test_returns_1_when_working_tree_dirty(self):
        with patch("git_sift.merger.check_working_tree_clean", return_value=False):
            assert prompt_and_merge() == 1

    def test_returns_1_when_no_pr(self):
        with (
            patch("git_sift.merger.check_working_tree_clean", return_value=True),
            patch("git_sift.merger.check_pr_exists", return_value=None),
        ):
            assert prompt_and_merge() == 1

    def test_returns_1_on_cancel(self):
        with (
            patch("git_sift.merger.check_working_tree_clean", return_value=True),
            patch("git_sift.merger.check_pr_exists", return_value=self._open_pr()),
            patch("git_sift.merger.Prompt.ask", return_value="c"),
        ):
            assert prompt_and_merge() == 1

    def test_squash_merge_success(self):
        merge_result = MagicMock(returncode=0)
        with (
            patch("git_sift.merger.check_working_tree_clean", return_value=True),
            patch("git_sift.merger.check_pr_exists", return_value=self._open_pr()),
            patch("git_sift.merger.Prompt.ask", return_value="s"),
            patch("git_sift.merger.subprocess.run", return_value=merge_result),
        ):
            assert prompt_and_merge() == 0

    def test_merge_commit_success(self):
        merge_result = MagicMock(returncode=0)
        with (
            patch("git_sift.merger.check_working_tree_clean", return_value=True),
            patch("git_sift.merger.check_pr_exists", return_value=self._open_pr()),
            patch("git_sift.merger.Prompt.ask", return_value="m"),
            patch("git_sift.merger.subprocess.run", return_value=merge_result),
        ):
            assert prompt_and_merge() == 0

    def test_rebase_merge_success(self):
        merge_result = MagicMock(returncode=0)
        with (
            patch("git_sift.merger.check_working_tree_clean", return_value=True),
            patch("git_sift.merger.check_pr_exists", return_value=self._open_pr()),
            patch("git_sift.merger.Prompt.ask", return_value="r"),
            patch("git_sift.merger.subprocess.run", return_value=merge_result),
        ):
            assert prompt_and_merge() == 0

    def test_merge_failure_returns_1(self):
        merge_result = MagicMock(returncode=1)
        with (
            patch("git_sift.merger.check_working_tree_clean", return_value=True),
            patch("git_sift.merger.check_pr_exists", return_value=self._open_pr()),
            patch("git_sift.merger.Prompt.ask", return_value="s"),
            patch("git_sift.merger.subprocess.run", return_value=merge_result),
        ):
            assert prompt_and_merge() == 1

    def test_invalid_merge_choice_returns_1(self):
        with (
            patch("git_sift.merger.check_working_tree_clean", return_value=True),
            patch("git_sift.merger.check_pr_exists", return_value=self._open_pr()),
            patch("git_sift.merger.Prompt.ask", return_value="z"),
        ):
            assert prompt_and_merge() == 1
