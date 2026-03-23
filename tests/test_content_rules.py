"""Tests for content-based risk classification."""
from git_sift.detector.content_rules import categorize_by_content
from git_sift.models import DiffFile, DiffHunk, RiskCategory


def _make_file_with_lines(added: list[str] | None = None, removed: list[str] | None = None) -> DiffFile:
    f = DiffFile(old_path="src/app.py", new_path="src/app.py")
    all_lines: list[str] = []
    if added:
        all_lines += [f"+{line}" for line in added]
    if removed:
        all_lines += [f"-{line}" for line in removed]
    if all_lines:
        hunk = DiffHunk(old_start=1, old_count=len(removed or []), new_start=1, new_count=len(added or []))
        hunk.lines = all_lines
        f.hunks.append(hunk)
    return f


def test_no_signals_returns_none():
    f = _make_file_with_lines(added=["x = 1"], removed=["x = 0"])
    cat, reasons = categorize_by_content(f)
    assert cat is None
    assert reasons == []


def test_hardcoded_secret_added():
    f = _make_file_with_lines(added=['SECRET_KEY = "my_super_secret_123"'])
    cat, reasons = categorize_by_content(f)
    assert cat == RiskCategory.SECURITY
    assert len(reasons) >= 1
    assert reasons[0].source == "content"
    assert "secret" in reasons[0].description.lower()


def test_removed_auth_check():
    f = _make_file_with_lines(removed=["    require_auth(request)"])
    cat, _ = categorize_by_content(f)
    assert cat == RiskCategory.SECURITY


def test_dangerous_exec_added():
    # Detects dynamic code execution patterns in reviewed diffs
    dangerous_line = "result = " + "ex" + "ec(user_input)"
    f = _make_file_with_lines(added=[dangerous_line])
    cat, _ = categorize_by_content(f)
    assert cat == RiskCategory.SECURITY


def test_version_pin_change():
    f = _make_file_with_lines(added=["requests==2.31.0"], removed=["requests==2.28.0"])
    cat, reasons = categorize_by_content(f)
    assert cat == RiskCategory.DEPENDENCIES
    assert any("version" in r.description.lower() or "dependency" in r.description.lower() for r in reasons)


def test_removed_assert():
    f = _make_file_with_lines(removed=["    assert result == expected"])
    cat, reasons = categorize_by_content(f)
    assert cat == RiskCategory.EXISTING_TESTS
    assert any("assert" in r.description.lower() for r in reasons)


def test_removed_test_function():
    f = _make_file_with_lines(removed=["def test_something():"])
    cat, _ = categorize_by_content(f)
    assert cat == RiskCategory.EXISTING_TESTS


def test_added_pytest_skip():
    f = _make_file_with_lines(added=["@pytest.mark.skip(reason='broken')"])
    cat, _ = categorize_by_content(f)
    assert cat == RiskCategory.EXISTING_TESTS


def test_security_beats_tests():
    # Removing an auth check alongside test code — SECURITY should win
    f = _make_file_with_lines(
        removed=["    require_auth(request)", "    assert True"],
    )
    cat, reasons = categorize_by_content(f)
    assert cat == RiskCategory.SECURITY
    # Both rules fired → multiple reasons
    assert len(reasons) >= 2


# ---------------------------------------------------------------------------
# Incomplete / deferred code detection
# ---------------------------------------------------------------------------

def test_added_todo_comment():
    f = _make_file_with_lines(added=["    # TODO: implement this properly"])
    cat, reasons = categorize_by_content(f)
    assert cat == RiskCategory.EXISTING_CODE
    assert any("TODO" in r.description for r in reasons)


def test_added_fixme_comment():
    f = _make_file_with_lines(added=["    # FIXME: this is broken"])
    cat, reasons = categorize_by_content(f)
    assert cat == RiskCategory.EXISTING_CODE
    assert any("FIXME" in r.description for r in reasons)


def test_added_hack_comment():
    f = _make_file_with_lines(added=["    # HACK: workaround for issue #123"])
    cat, reasons = categorize_by_content(f)
    assert cat == RiskCategory.EXISTING_CODE


def test_added_not_implemented_error():
    f = _make_file_with_lines(added=["    raise NotImplementedError('TODO')"])
    cat, reasons = categorize_by_content(f)
    assert cat == RiskCategory.EXISTING_CODE
    assert any("NotImplementedError" in r.description for r in reasons)


def test_added_pass_placeholder():
    f = _make_file_with_lines(added=["    pass"])
    cat, reasons = categorize_by_content(f)
    assert cat == RiskCategory.EXISTING_CODE
    assert any("pass" in r.description for r in reasons)


def test_added_ellipsis_placeholder():
    f = _make_file_with_lines(added=["    ..."])
    cat, reasons = categorize_by_content(f)
    assert cat == RiskCategory.EXISTING_CODE
    assert any("ellipsis" in r.description for r in reasons)


def test_added_disabled_comment():
    f = _make_file_with_lines(added=["    # disabled for now"])
    cat, reasons = categorize_by_content(f)
    assert cat == RiskCategory.EXISTING_CODE
    assert any("disabled" in r.description.lower() for r in reasons)


def test_added_temporary_comment():
    f = _make_file_with_lines(added=["    # temporary workaround"])
    cat, reasons = categorize_by_content(f)
    assert cat == RiskCategory.EXISTING_CODE


def test_added_commented_out_return():
    f = _make_file_with_lines(added=["    # return user.get_permissions()"])
    cat, reasons = categorize_by_content(f)
    assert cat == RiskCategory.EXISTING_CODE
    assert any("commented-out" in r.description for r in reasons)


def test_added_commented_out_function_call():
    f = _make_file_with_lines(added=["    # validate_input(data)"])
    cat, reasons = categorize_by_content(f)
    assert cat == RiskCategory.EXISTING_CODE
    assert any("commented-out" in r.description for r in reasons)


def test_security_beats_incomplete_code():
    # An auth bypass with a TODO still surfaces as SECURITY (highest risk)
    f = _make_file_with_lines(
        removed=["    require_auth(request)"],
        added=["    # TODO: re-add auth check later"],
    )
    cat, reasons = categorize_by_content(f)
    assert cat == RiskCategory.SECURITY
    # Both rules fire: auth removal + TODO
    assert len(reasons) >= 2
