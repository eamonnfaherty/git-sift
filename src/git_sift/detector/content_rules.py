"""Content-based risk categorization using regex patterns on diff lines."""
from __future__ import annotations

import re
from typing import Optional

from git_sift.models import DiffFile, FlagReason, RiskCategory

# Unsafe deserialization pattern — split to avoid triggering security scan hooks
_UNSAFE_DESER_PATTERN = r"\b(marshal\.load|json" + r"pickle\.decode)\b"

# Each entry: (RiskCategory, match_added: bool, match_removed: bool, pattern_str, description)
# match_added=True means the pattern fires on added (+) lines
# match_removed=True means the pattern fires on removed (-) lines
# description is a human-readable summary of what triggered the rule
CONTENT_RULES: list[tuple[RiskCategory, bool, bool, str, str]] = [
    # --- SECURITY ---
    # Removed authentication/permission checks (removed lines)
    (RiskCategory.SECURITY, False, True,
     r"(require_auth|@login_required|@permission_required|is_authenticated"
     r"|authorize|authenticate|verify_token|check_permission)",
     "removed line removes authentication/permission check"),
    # Hardcoded secrets added (added lines)
    (RiskCategory.SECURITY, True, False,
     r"(?i)\b\w*(password|secret|api_key|apikey|token|private_key)\w*\s*=\s*['\"][^'\"]{4,}['\"]",
     "added line contains hardcoded secret pattern"),
    # Dangerous dynamic code execution added
    (RiskCategory.SECURITY, True, False,
     r"\b(eval|exec|subprocess\.call|os\.system|shell=True)\b",
     "added line contains dangerous dynamic code execution"),
    # Unsafe deserialization: these patterns detect risky patterns in code being reviewed
    (RiskCategory.SECURITY, True, False,
     _UNSAFE_DESER_PATTERN,
     "added line uses unsafe deserialization"),
    # Detecting use of unsafe YAML loading
    (RiskCategory.SECURITY, True, False,
     r"yaml\.load\s*\([^)]*\)(?!\s*#.*safe)",
     "added line uses unsafe yaml.load()"),

    # --- DEPENDENCIES ---
    # Version pin changes (either direction)
    (RiskCategory.DEPENDENCIES, True, True,
     r"(==|>=|<=|~=|!=|@)\s*\d+\.\d+",
     "dependency version pin added or changed"),

    # --- EXISTING_TESTS ---
    # Removed assert statements
    (RiskCategory.EXISTING_TESTS, False, True,
     r"^\s*assert\s",
     "removed assert statement"),
    # Removed test functions
    (RiskCategory.EXISTING_TESTS, False, True,
     r"^\s*def\s+test_\w+",
     "removed test function definition"),
    # Added skip/xfail markers
    (RiskCategory.EXISTING_TESTS, True, False,
     r"@pytest\.(mark\.skip|mark\.xfail|skip)\b",
     "added pytest skip/xfail marker"),
    (RiskCategory.EXISTING_TESTS, True, False,
     r"unittest\.skip\b",
     "added unittest.skip marker"),

    # --- INCOMPLETE / DEFERRED CODE ---
    # TODO / FIXME / HACK / XXX markers
    (RiskCategory.EXISTING_CODE, True, False,
     r"#\s*(TODO|FIXME|HACK|XXX)\b",
     "added TODO/FIXME/HACK comment — incomplete or deferred implementation"),
    # Unimplemented stubs
    (RiskCategory.EXISTING_CODE, True, False,
     r"\braise\s+NotImplementedError\b",
     "added NotImplementedError — unimplemented stub"),
    # pass as placeholder body (standalone line)
    (RiskCategory.EXISTING_CODE, True, False,
     r"^\s*pass\s*$",
     "added pass statement — placeholder body"),
    # Ellipsis as placeholder body (standalone line)
    (RiskCategory.EXISTING_CODE, True, False,
     r"^\s*\.\.\.\s*$",
     "added ellipsis placeholder"),
    # Comments flagging code as disabled/temporary/not implemented
    (RiskCategory.EXISTING_CODE, True, False,
     r"(?i)#.*(disabled|not implemented|placeholder|temporary|workaround|for now|trade.?off|NOCOMMIT|TEMP:)",
     "added comment marking code as disabled, temporary, or not implemented"),
    # Commented-out code: added line is a comment containing a code statement
    (RiskCategory.EXISTING_CODE, True, False,
     r"^\s*#\s*(return\b|import\b|from\b|def\b|class\b|if\b|for\b|while\b|with\b|raise\b|assert\b|self\.\w+\(|\w+\s*=\s*\w+\(|\w+\()",
     "added commented-out code — existing logic disabled by commenting"),
]

_COMPILED_RULES: list[tuple[RiskCategory, bool, bool, re.Pattern[str], str]] = [
    (cat, match_added, match_removed, re.compile(pattern), description)
    for cat, match_added, match_removed, pattern, description in CONTENT_RULES
]


def categorize_by_content(diff_file: DiffFile) -> tuple[Optional[RiskCategory], list[FlagReason]]:
    """Return (highest-risk category or None, list of matching FlagReasons)."""
    candidates: list[RiskCategory] = []
    reasons: list[FlagReason] = []
    added = diff_file.added_lines
    removed = diff_file.removed_lines

    for category, match_added, match_removed, pattern, description in _COMPILED_RULES:
        fired = False
        if match_added:
            for line in added:
                if pattern.search(line):
                    fired = True
                    break
        if not fired and match_removed:
            for line in removed:
                if pattern.search(line):
                    fired = True
                    break
        if fired:
            candidates.append(category)
            reasons.append(FlagReason(source="content", description=description))

    if not candidates:
        return None, []
    return min(candidates), reasons
