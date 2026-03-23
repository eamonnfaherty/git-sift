"""Tests for the interactive file browser."""
from unittest.mock import MagicMock, patch

import pytest

from git_sift.browser import _build_claude_prompt, run_browser
from git_sift.models import (
    BrowserResult,
    DiffFile,
    DiffMode,
    DiffOptions,
    FileReview,
    FlagReason,
    RiskCategory,
)


def _make_review(
    path: str = "src/app.py",
    category: RiskCategory = RiskCategory.EXISTING_CODE,
    raw_diff: str = "@@ -1 +1 @@\n-old\n+new\n",
) -> FileReview:
    diff_file = DiffFile(
        old_path=path,
        new_path=path,
        raw_diff=raw_diff,
    )
    reasons = [FlagReason(source="path", description=f'path matches "{path}"')]
    return FileReview(diff_file=diff_file, category=category, reasons=reasons)


def _make_options() -> DiffOptions:
    return DiffOptions(mode=DiffMode.STAGED)


# ---------------------------------------------------------------------------
# _build_claude_prompt
# ---------------------------------------------------------------------------

class TestBuildClaudePrompt:
    def test_contains_file_path(self):
        review = _make_review(path="src/auth.py", category=RiskCategory.SECURITY)
        prompt = _build_claude_prompt(review, "Fix the auth check")
        assert "src/auth.py" in prompt

    def test_contains_recommendation(self):
        review = _make_review()
        prompt = _build_claude_prompt(review, "Add input validation")
        assert "Add input validation" in prompt

    def test_contains_diff(self):
        review = _make_review(raw_diff="@@ -1 +1 @@\n-bad\n+good\n")
        prompt = _build_claude_prompt(review, "Fix it")
        assert "-bad" in prompt
        assert "+good" in prompt

    def test_contains_ai_review_fix_instruction(self):
        review = _make_review()
        prompt = _build_claude_prompt(review, "Do something")
        assert "AI-REVIEW-FIX" in prompt

    def test_security_category_includes_security_instruction(self):
        review = _make_review(category=RiskCategory.SECURITY)
        prompt = _build_claude_prompt(review, "Fix vuln")
        assert "AI-REVIEW-FIX(SECURITY)" in prompt

    def test_non_security_category_omits_security_instruction(self):
        review = _make_review(category=RiskCategory.EXISTING_CODE)
        prompt = _build_claude_prompt(review, "Refactor")
        assert "AI-REVIEW-FIX(SECURITY)" not in prompt

    def test_category_label_in_prompt(self):
        review = _make_review(category=RiskCategory.DEPENDENCIES)
        prompt = _build_claude_prompt(review, "Update pin")
        assert "Dependencies" in prompt

    def test_risk_level_value_in_prompt(self):
        review = _make_review(category=RiskCategory.SECURITY)
        prompt = _build_claude_prompt(review, "Fix")
        # SECURITY = 1
        assert "1/10" in prompt or "level 1" in prompt


# ---------------------------------------------------------------------------
# run_browser
# ---------------------------------------------------------------------------

class TestRunBrowser:
    def test_empty_reviews_returns_all_approved(self):
        result = run_browser([], _make_options())
        assert result.all_approved is True
        assert result.recommendations_made is False

    def test_approve_all_files_returns_all_approved(self):
        reviews = [_make_review("a.py"), _make_review("b.py")]
        # Approve file 0, then file 1 (now at index 0 after wrap), then all approved
        with patch("git_sift.browser.Prompt.ask", side_effect=["a", "a"]):
            result = run_browser(reviews, _make_options())
        assert result.all_approved is True
        assert result.recommendations_made is False

    def test_recommend_triggers_restart_when_claude_available(self):
        reviews = [_make_review("a.py")]
        with (
            patch("git_sift.browser.check_claude_available", return_value=True),
            patch("git_sift.browser.run_claude", return_value=True),
            patch("git_sift.browser.Prompt.ask", side_effect=["r", "Fix the bug"]),
        ):
            result = run_browser(reviews, _make_options())
        assert result.recommendations_made is True
        assert result.all_approved is False

    def test_recommend_shows_error_when_claude_not_available(self):
        reviews = [_make_review("a.py")]
        # r → no claude → show error → a → approved
        with (
            patch("git_sift.browser.check_claude_available", return_value=False),
            patch("git_sift.browser.Prompt.ask", side_effect=["r", "a"]),
        ):
            result = run_browser(reviews, _make_options())
        assert result.recommendations_made is False
        assert result.all_approved is True

    def test_navigation_next_and_prev(self):
        reviews = [_make_review("a.py"), _make_review("b.py"), _make_review("c.py")]
        # n → n → p → approve current (b) → approve (c) → approve (a)
        with patch("git_sift.browser.Prompt.ask", side_effect=["n", "n", "p", "a", "a", "a"]):
            result = run_browser(reviews, _make_options())
        assert result.all_approved is True

    def test_skip_does_not_approve(self):
        reviews = [_make_review("a.py")]
        # s → a (must approve to exit)
        with patch("git_sift.browser.Prompt.ask", side_effect=["s", "a"]):
            result = run_browser(reviews, _make_options())
        assert result.all_approved is True

    def test_help_does_not_advance(self):
        reviews = [_make_review("a.py")]
        # ? → a
        with patch("git_sift.browser.Prompt.ask", side_effect=["?", "a"]):
            result = run_browser(reviews, _make_options())
        assert result.all_approved is True

    def test_invalid_input_does_not_advance(self):
        reviews = [_make_review("a.py")]
        # x (invalid) → a
        with patch("git_sift.browser.Prompt.ask", side_effect=["x", "a"]):
            result = run_browser(reviews, _make_options())
        assert result.all_approved is True
