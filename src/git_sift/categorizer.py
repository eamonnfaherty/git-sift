"""Assigns a RiskCategory to each DiffFile."""
from __future__ import annotations

from git_sift.detector.content_rules import categorize_by_content
from git_sift.detector.dep_extractor import extract_dep_changes
from git_sift.detector.path_rules import categorize_by_path
from git_sift.models import DiffFile, FlagReason, FileReview, RiskCategory


def categorize_file(diff_file: DiffFile) -> tuple[RiskCategory, list[FlagReason]]:
    """
    Assign the highest-risk (lowest integer) category to a file.

    Resolution order:
    1. path_result  — from path pattern matching
    2. content_result — from content regex matching
    3. min(path_result, content_result) if both present
    4. New-file upgrade: EXISTING_TESTS → NEW_TESTS when the file is brand new
    5. Fallback: NEW_CODE if is_new_file, else EXISTING_CODE

    Returns (category, reasons).
    """
    path_cat, path_reasons = categorize_by_path(diff_file.new_path)
    content_cat, content_reasons = categorize_by_content(diff_file)

    all_reasons: list[FlagReason] = path_reasons + content_reasons
    candidates = [c for c in (path_cat, content_cat) if c is not None]

    if candidates:
        final_cat = min(candidates)
        if final_cat == RiskCategory.DEPENDENCIES:
            all_reasons += extract_dep_changes(diff_file)
        # New file containing tests → NEW_TESTS (lower risk than modifying existing tests)
        if final_cat == RiskCategory.EXISTING_TESTS and diff_file.is_new_file:
            all_reasons.append(FlagReason(
                source="content",
                description="new file → New Tests",
            ))
            final_cat = RiskCategory.NEW_TESTS
        return final_cat, all_reasons

    # Fallback
    if diff_file.is_new_file:
        fallback_reason = FlagReason(source="fallback", description="new file, no other rules matched → New Code")
        return RiskCategory.NEW_CODE, [fallback_reason]
    fallback_reason = FlagReason(source="fallback", description="no rules matched → Existing Code")
    return RiskCategory.EXISTING_CODE, [fallback_reason]


def categorize_all(diff_files: list[DiffFile]) -> list[FileReview]:
    """Return a list of FileReview objects with categories and reasons assigned."""
    return [
        FileReview(diff_file=f, category=cat, reasons=reasons)
        for f in diff_files
        for cat, reasons in (categorize_file(f),)
    ]
