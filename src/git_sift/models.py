from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Optional


class RiskCategory(IntEnum):
    """Risk categories ordered from highest (1) to lowest (11) risk."""
    SECURITY = 1
    DEPENDENCIES = 2
    INFRASTRUCTURE = 3
    DATABASE_MIGRATIONS = 4
    ARCH_TESTS = 5
    EXISTING_TESTS = 6
    NEW_TESTS = 7
    EXISTING_CODE = 8
    NEW_CODE = 9
    CONFIG_ENV = 10
    DOCS_FORMATTING = 11


CATEGORY_LABELS = {
    RiskCategory.SECURITY: "Security",
    RiskCategory.DEPENDENCIES: "Dependencies",
    RiskCategory.INFRASTRUCTURE: "Infrastructure",
    RiskCategory.DATABASE_MIGRATIONS: "Database Migrations",
    RiskCategory.ARCH_TESTS: "Architecture Tests",
    RiskCategory.EXISTING_TESTS: "Existing Tests",
    RiskCategory.NEW_TESTS: "New Tests",
    RiskCategory.EXISTING_CODE: "Existing Code",
    RiskCategory.NEW_CODE: "New Code",
    RiskCategory.CONFIG_ENV: "Config / Environment",
    RiskCategory.DOCS_FORMATTING: "Docs & Formatting",
}

CATEGORY_COLORS = {
    RiskCategory.SECURITY: "bold red",
    RiskCategory.DEPENDENCIES: "red",
    RiskCategory.INFRASTRUCTURE: "dark_orange",
    RiskCategory.DATABASE_MIGRATIONS: "orange1",
    RiskCategory.ARCH_TESTS: "yellow",
    RiskCategory.EXISTING_TESTS: "yellow",
    RiskCategory.NEW_TESTS: "cyan",
    RiskCategory.EXISTING_CODE: "green",
    RiskCategory.NEW_CODE: "cyan",
    RiskCategory.CONFIG_ENV: "blue",
    RiskCategory.DOCS_FORMATTING: "bright_black",
}


CATEGORY_ALIASES: dict[str, RiskCategory] = {
    "security": RiskCategory.SECURITY,
    "dependencies": RiskCategory.DEPENDENCIES,
    "dependency": RiskCategory.DEPENDENCIES,
    "infrastructure": RiskCategory.INFRASTRUCTURE,
    "infra": RiskCategory.INFRASTRUCTURE,
    "database": RiskCategory.DATABASE_MIGRATIONS,
    "database-migrations": RiskCategory.DATABASE_MIGRATIONS,
    "migrations": RiskCategory.DATABASE_MIGRATIONS,
    "arch-tests": RiskCategory.ARCH_TESTS,
    "arch": RiskCategory.ARCH_TESTS,
    "existing-tests": RiskCategory.EXISTING_TESTS,
    "tests": RiskCategory.EXISTING_TESTS,
    "new-tests": RiskCategory.NEW_TESTS,
    "existing-code": RiskCategory.EXISTING_CODE,
    "code": RiskCategory.EXISTING_CODE,
    "new-code": RiskCategory.NEW_CODE,
    "new": RiskCategory.NEW_CODE,
    "config": RiskCategory.CONFIG_ENV,
    "config-env": RiskCategory.CONFIG_ENV,
    "env": RiskCategory.CONFIG_ENV,
    "docs": RiskCategory.DOCS_FORMATTING,
    "docs-formatting": RiskCategory.DOCS_FORMATTING,
    "formatting": RiskCategory.DOCS_FORMATTING,
}


class ReviewDecision(Enum):
    APPROVE = "approve"
    CONCERN = "concern"
    BLOCKER = "blocker"
    SKIP = "skip"
    MENU = "menu"  # internal: go to category menu


class DiffMode(Enum):
    STAGED = "staged"
    UNSTAGED = "unstaged"
    REFS = "refs"


@dataclass
class DiffHunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[str] = field(default_factory=list)


@dataclass
class DiffFile:
    old_path: str
    new_path: str
    hunks: list[DiffHunk] = field(default_factory=list)
    is_new_file: bool = False
    is_deleted: bool = False
    is_rename: bool = False
    raw_diff: str = ""

    @property
    def display_path(self) -> str:
        if self.is_rename:
            return f"{self.old_path} -> {self.new_path}"
        if self.is_deleted:
            return self.old_path
        return self.new_path

    @property
    def added_lines(self) -> list[str]:
        result = []
        for hunk in self.hunks:
            for line in hunk.lines:
                if line.startswith("+"):
                    result.append(line[1:])
        return result

    @property
    def removed_lines(self) -> list[str]:
        result = []
        for hunk in self.hunks:
            for line in hunk.lines:
                if line.startswith("-"):
                    result.append(line[1:])
        return result


@dataclass
class FlagReason:
    """Records why a file was assigned its risk category."""
    source: str        # "path", "content", or "fallback"
    description: str   # human-readable explanation


@dataclass
class FileReview:
    diff_file: DiffFile
    category: RiskCategory
    decision: Optional[ReviewDecision] = None
    note: Optional[str] = None
    reasons: list["FlagReason"] = field(default_factory=list)


@dataclass
class DiffOptions:
    mode: DiffMode
    ref_a: Optional[str] = None
    ref_b: Optional[str] = None


@dataclass
class ReviewSession:
    options: DiffOptions
    reviews: list[FileReview] = field(default_factory=list)


@dataclass
class BrowserResult:
    all_approved: bool = False
    recommendations_made: bool = False


@dataclass
class SessionSummary:
    per_category: dict[RiskCategory, dict[str, int]]
    blockers: list[FileReview]
    concerns: list[FileReview]

    @property
    def has_blockers(self) -> bool:
        return len(self.blockers) > 0
