"""Tests for non-interactive --fail-on mode."""
from unittest.mock import patch

import click
import pytest

from git_sift.cli import _parse_fail_on
from git_sift.models import DiffMode, DiffOptions, RiskCategory
from git_sift.wizard import run_check, run_summarize


# ---------------------------------------------------------------------------
# _parse_fail_on
# ---------------------------------------------------------------------------

class TestParseFailOn:
    def test_single_name(self):
        assert _parse_fail_on("security") == {RiskCategory.SECURITY}

    def test_aliases(self):
        assert _parse_fail_on("dependency") == {RiskCategory.DEPENDENCIES}
        assert _parse_fail_on("dependencies") == {RiskCategory.DEPENDENCIES}
        assert _parse_fail_on("infra") == {RiskCategory.INFRASTRUCTURE}
        assert _parse_fail_on("migrations") == {RiskCategory.DATABASE_MIGRATIONS}
        assert _parse_fail_on("tests") == {RiskCategory.EXISTING_TESTS}
        assert _parse_fail_on("docs") == {RiskCategory.DOCS_FORMATTING}
        assert _parse_fail_on("config") == {RiskCategory.CONFIG_ENV}

    def test_multiple_names(self):
        result = _parse_fail_on("security,dependency")
        assert result == {RiskCategory.SECURITY, RiskCategory.DEPENDENCIES}

    def test_numeric_level(self):
        assert _parse_fail_on("1") == {RiskCategory.SECURITY}
        assert _parse_fail_on("2") == {RiskCategory.DEPENDENCIES}

    def test_mixed_names_and_levels(self):
        result = _parse_fail_on("security,2")
        assert result == {RiskCategory.SECURITY, RiskCategory.DEPENDENCIES}

    def test_case_insensitive(self):
        assert _parse_fail_on("SECURITY") == {RiskCategory.SECURITY}
        assert _parse_fail_on("Security") == {RiskCategory.SECURITY}

    def test_whitespace_around_tokens(self):
        assert _parse_fail_on(" security , dependency ") == {
            RiskCategory.SECURITY,
            RiskCategory.DEPENDENCIES,
        }

    def test_unknown_name_raises(self):
        with pytest.raises(click.BadParameter, match="unknown category"):
            _parse_fail_on("notacategory")

    def test_unknown_level_raises(self):
        with pytest.raises(click.BadParameter, match="unknown risk level"):
            _parse_fail_on("99")

    def test_deduplication(self):
        # security and dependency are the same regardless of alias used
        result = _parse_fail_on("security,security")
        assert result == {RiskCategory.SECURITY}


# ---------------------------------------------------------------------------
# run_check
# ---------------------------------------------------------------------------

def _make_options() -> DiffOptions:
    return DiffOptions(mode=DiffMode.STAGED)


RAW_DIFF_SECURITY = """\
diff --git a/src/auth.py b/src/auth.py
--- a/src/auth.py
+++ b/src/auth.py
@@ -1,3 +1,3 @@
-require_auth(request)
+pass
"""

RAW_DIFF_DOCS = """\
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1,1 +1,1 @@
-old text
+new text
"""


class TestRunCheck:
    def _run(self, raw_diff: str, fail_on: set[RiskCategory]) -> int:
        with (
            patch("git_sift.wizard.assert_in_git_repo"),
            patch("git_sift.wizard.fetch_diff", return_value=raw_diff),
        ):
            return run_check(_make_options(), fail_on)

    def test_returns_0_when_no_diff(self):
        result = self._run("", {RiskCategory.SECURITY})
        assert result == 0

    def test_returns_1_when_matching_category(self):
        result = self._run(RAW_DIFF_SECURITY, {RiskCategory.SECURITY})
        assert result == 1

    def test_returns_0_when_category_not_in_fail_on(self):
        # Security diff but only docs is in fail-on
        result = self._run(RAW_DIFF_SECURITY, {RiskCategory.DOCS_FORMATTING})
        assert result == 0

    def test_returns_0_when_only_docs_changed_and_fail_on_security(self):
        result = self._run(RAW_DIFF_DOCS, {RiskCategory.SECURITY})
        assert result == 0

    def test_returns_1_when_docs_changed_and_fail_on_docs(self):
        result = self._run(RAW_DIFF_DOCS, {RiskCategory.DOCS_FORMATTING})
        assert result == 1

    def test_multiple_fail_on_categories(self):
        result = self._run(
            RAW_DIFF_SECURITY,
            {RiskCategory.SECURITY, RiskCategory.DEPENDENCIES},
        )
        assert result == 1


# ---------------------------------------------------------------------------
# run_summarize
# ---------------------------------------------------------------------------

class TestRunSummarize:
    def _run(self, raw_diff: str) -> int:
        with (
            patch("git_sift.wizard.assert_in_git_repo"),
            patch("git_sift.wizard.fetch_diff", return_value=raw_diff),
        ):
            return run_summarize(_make_options())

    def test_returns_0_when_no_diff(self):
        assert self._run("") == 0

    def test_returns_0_with_changes(self):
        assert self._run(RAW_DIFF_SECURITY) == 0

    def test_returns_0_with_docs_changes(self):
        assert self._run(RAW_DIFF_DOCS) == 0

    def test_returns_0_with_multiple_files(self):
        combined = RAW_DIFF_SECURITY + "\n" + RAW_DIFF_DOCS
        assert self._run(combined) == 0
