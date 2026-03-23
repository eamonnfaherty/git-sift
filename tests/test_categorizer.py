"""Tests for the file categorizer."""
from git_sift.categorizer import categorize_file
from git_sift.models import DiffFile, RiskCategory


def _make_file(
    path: str,
    is_new: bool = False,
    added: list[str] | None = None,
    removed: list[str] | None = None,
) -> DiffFile:
    from git_sift.models import DiffHunk
    f = DiffFile(old_path=path, new_path=path, is_new_file=is_new)
    lines = []
    if added:
        lines += [f"+{line}" for line in added]
    if removed:
        lines += [f"-{line}" for line in removed]
    if lines:
        hunk = DiffHunk(old_start=1, old_count=len(removed or []), new_start=1, new_count=len(added or []))
        hunk.lines = lines
        f.hunks.append(hunk)
    return f


def test_new_file_fallback():
    f = _make_file("src/utils.py", is_new=True)
    cat, reasons = categorize_file(f)
    assert cat == RiskCategory.NEW_CODE
    assert len(reasons) == 1
    assert reasons[0].source == "fallback"


def test_existing_file_fallback():
    f = _make_file("src/utils.py", is_new=False)
    cat, reasons = categorize_file(f)
    assert cat == RiskCategory.EXISTING_CODE
    assert len(reasons) == 1
    assert reasons[0].source == "fallback"


def test_docs_path():
    f = _make_file("README.md")
    cat, _ = categorize_file(f)
    assert cat == RiskCategory.DOCS_FORMATTING


def test_security_path():
    f = _make_file("src/auth/middleware.py")
    cat, _ = categorize_file(f)
    assert cat == RiskCategory.SECURITY


def test_dependencies_path():
    f = _make_file("requirements.txt")
    cat, _ = categorize_file(f)
    assert cat == RiskCategory.DEPENDENCIES


def test_infrastructure_path():
    f = _make_file("Dockerfile")
    cat, _ = categorize_file(f)
    assert cat == RiskCategory.INFRASTRUCTURE


def test_migrations_path():
    f = _make_file("migrations/0001_initial.py")
    cat, _ = categorize_file(f)
    assert cat == RiskCategory.DATABASE_MIGRATIONS


def test_test_file_path():
    f = _make_file("tests/test_user.py")
    cat, _ = categorize_file(f)
    assert cat == RiskCategory.EXISTING_TESTS


def test_content_overrides_path_when_higher_risk():
    # A test file that adds a hardcoded secret → should be SECURITY not EXISTING_TESTS
    f = _make_file("tests/test_auth.py", added=['API_KEY = "hardcoded_secret_value"'])
    cat, reasons = categorize_file(f)
    assert cat == RiskCategory.SECURITY
    # Should have reasons from both path and content
    sources = {r.source for r in reasons}
    assert "path" in sources
    assert "content" in sources


def test_path_wins_over_content_when_higher_risk():
    # requirements.txt with no version changes → DEPENDENCIES (path), no content signal
    f = _make_file("requirements.txt")
    cat, _ = categorize_file(f)
    assert cat == RiskCategory.DEPENDENCIES


# ── New-file upgrade: EXISTING_TESTS → NEW_TESTS ─────────────────────────────

def test_new_test_file_becomes_new_tests():
    f = _make_file("tests/test_user.py", is_new=True, added=["def test_something(): pass"])
    cat, reasons = categorize_file(f)
    assert cat == RiskCategory.NEW_TESTS
    assert any("New Tests" in r.description for r in reasons)


def test_existing_test_file_with_additions_stays_existing_tests():
    # Adding lines to an existing test file is a modification — EXISTING_TESTS
    f = _make_file("tests/test_user.py", added=["def test_new(): pass"])
    cat, _ = categorize_file(f)
    assert cat == RiskCategory.EXISTING_TESTS


def test_existing_test_file_with_removals_stays_existing_tests():
    f = _make_file("tests/test_user.py", added=["def test_new(): pass"], removed=["def test_old(): pass"])
    cat, _ = categorize_file(f)
    assert cat == RiskCategory.EXISTING_TESTS


# ── New-file upgrade: NEW_CODE for new non-test files ────────────────────────

def test_new_code_file_is_new_code():
    # Handled by fallback: new file with no path rules → NEW_CODE
    f = _make_file("src/utils.py", is_new=True)
    cat, reasons = categorize_file(f)
    assert cat == RiskCategory.NEW_CODE
    assert reasons[0].source == "fallback"


def test_existing_code_file_with_additions_is_existing_code():
    # Adding lines to existing file is still EXISTING_CODE
    f = _make_file("src/utils.py", added=["def helper(): pass"])
    cat, _ = categorize_file(f)
    assert cat == RiskCategory.EXISTING_CODE


def test_existing_code_file_with_modifications_is_existing_code():
    f = _make_file("src/utils.py", added=["def new_fn(): pass"], removed=["def old_fn(): pass"])
    cat, _ = categorize_file(f)
    assert cat == RiskCategory.EXISTING_CODE


def test_higher_risk_path_not_downgraded():
    # Security file — new or not, must stay SECURITY
    f = _make_file("src/auth.py", is_new=True, added=["def login(): pass"])
    cat, _ = categorize_file(f)
    assert cat == RiskCategory.SECURITY
