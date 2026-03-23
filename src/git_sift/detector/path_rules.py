"""Path-based risk categorization using fnmatch patterns."""
from __future__ import annotations

import fnmatch
from typing import Optional

from git_sift.models import CATEGORY_LABELS, FlagReason, RiskCategory

# Each entry: (RiskCategory, list_of_patterns)
# Patterns are matched against the file path (new_path or old_path)
PATH_RULES: list[tuple[RiskCategory, list[str]]] = [
    (RiskCategory.SECURITY, [
        "*auth*",
        "*secret*",
        "*jwt*",
        "*.pem",
        "*.key",
        "*.crt",
        "*/secrets/*",
        "*credential*",
        "*password*",
        "*token*",
    ]),
    (RiskCategory.DEPENDENCIES, [
        "requirements*.txt",
        "pyproject.toml",
        "setup.cfg",
        "setup.py",
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "go.mod",
        "go.sum",
        "Cargo.toml",
        "Cargo.lock",
        "Gemfile",
        "Gemfile.lock",
        "composer.json",
        "composer.lock",
        "*.csproj",
        "*.nuspec",
    ]),
    (RiskCategory.INFRASTRUCTURE, [
        "Dockerfile",
        "Dockerfile.*",
        "docker-compose*.yml",
        "docker-compose*.yaml",
        ".github/workflows/*",
        ".gitlab-ci.yml",
        ".circleci/*",
        "*.tf",
        "*.tfvars",
        "kubernetes/*",
        "k8s/*",
        "helm/*",
        "charts/*",
        "*.nomad",
        "Makefile",
        "*.sh",
    ]),
    (RiskCategory.DATABASE_MIGRATIONS, [
        "migrations/*",
        "*/migrations/*",
        "alembic/versions/*",
        "*/alembic/versions/*",
        "*.migration.sql",
        "db/migrate/*",
        "*/db/migrate/*",
        "flyway/*",
        "*/flyway/*",
    ]),
    (RiskCategory.ARCH_TESTS, [
        "*arch*test*",
        "*test*arch*",
        "tests/arch/*",
        "test/arch/*",
        "*architecture*test*",
    ]),
    (RiskCategory.EXISTING_TESTS, [
        "test_*.py",
        "*_test.py",
        "*.test.ts",
        "*.test.tsx",
        "*.test.js",
        "*.test.jsx",
        "*.spec.ts",
        "*.spec.tsx",
        "*.spec.js",
        "*.spec.jsx",
        "__tests__/*",
        "tests/*",
        "test/*",
    ]),
    (RiskCategory.CONFIG_ENV, [
        "*.env",
        ".env",
        ".env.*",
        "*.ini",
        "*.cfg",
        "*.conf",
        "*.yaml",
        "*.yml",
        "settings*.py",
        "config*.py",
        "config/*",
        "*/config/*",
        "*.toml",
    ]),
    (RiskCategory.DOCS_FORMATTING, [
        "*.md",
        "*.rst",
        "*.txt",
        "docs/*",
        "doc/*",
        "documentation/*",
        "*.adoc",
        "CHANGELOG*",
        "README*",
        "LICENSE*",
        "CONTRIBUTING*",
    ]),
]


def categorize_by_path(path: str) -> tuple[Optional[RiskCategory], list[FlagReason]]:
    """Return (highest-risk category or None, list of matching FlagReasons)."""
    candidates: list[RiskCategory] = []
    reasons: list[FlagReason] = []
    for category, patterns in PATH_RULES:
        for pattern in patterns:
            # Match against full path and just the filename
            filename = path.split("/")[-1] if "/" in path else path
            if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(filename, pattern):
                candidates.append(category)
                label = CATEGORY_LABELS.get(category, str(category))
                reasons.append(FlagReason(
                    source="path",
                    description=f'path matches "{pattern}" \u2192 {label}',
                ))
                break
    if not candidates:
        return None, []
    return min(candidates), reasons
