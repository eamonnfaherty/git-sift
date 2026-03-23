"""Extract human-readable descriptions of individual dependency changes from a diff."""
from __future__ import annotations

import re

from git_sift.models import DiffFile, FlagReason

# Lines that are structural noise in dependency files — skip them
_NOISE = re.compile(
    r"""
    ^\s*$                           |   # blank
    ^\s*\#                          |   # comment  (requirements.txt, Cargo.toml)
    ^\s*//                          |   # comment  (go.mod, package-lock.json)
    ^\s*[\{\}\(\)\[\]]              |   # braces / brackets / parens
    ^\s*module\s                    |   # go.mod: module directive
    ^\s*go\s+\d                     |   # go.mod: go version line
    ^\s*require\s*[\(\{]?\s*$       |   # go.mod: bare 'require' or 'require ('
    ^\s*toolchain\s                 |   # go.mod: toolchain directive
    ^\s*"name"\s*:                  |   # package.json: name
    ^\s*"version"\s*:               |   # package.json: version
    ^\s*"description"\s*:           |   # package.json: description field
    ^\s*"(main|scripts|license|author|repository|keywords|private|type)"\s*:
    """,
    re.VERBOSE,
)

# pyproject.toml-specific: TOML key=value metadata/config lines to skip
_PYPROJECT_METADATA_KEY = re.compile(
    r"""
    ^\s*(
        name | version | description | readme | license | authors? | maintainers? |
        keywords | classifiers? | urls? | requires-python | build-backend |
        backend-path | packages | include | exclude | dynamic |
        line-length | indent-width | target-version | select | ignore |
        extend-select | extend-ignore | fixable | unfixable | per-file-ignores |
        format | quote-style | indent-style | skip-magic-trailing-comma |
        line-ending | docstring-code-format | docstring-code-line-length |
        testpaths | filterwarnings | addopts | markers
    )\s*=
    """,
    re.VERBOSE,
)

# pyproject.toml dep line: a PEP 508 package spec quoted in a list, e.g. "requests>=2.31.0"
_PYPROJECT_PEP508 = re.compile(r"""^\s*"[A-Za-z0-9][^"]*"$""")

# poetry-style dep: `package = "version-spec"` where value starts with a version indicator
_POETRY_DEP = re.compile(r"""^\s*[\w][\w\-\.]*\s*=\s*"[~^>=<!\d\*]""")


def _is_pyproject_dep(line: str) -> bool:
    """Return True only for lines that represent actual dependency changes in pyproject.toml."""
    if _PYPROJECT_METADATA_KEY.match(line):
        return False
    # Accept PEP 508 quoted spec (inside a dep list) or poetry-style versioned dep
    return bool(_PYPROJECT_PEP508.match(line) or _POETRY_DEP.match(line))

# Trailing noise to strip from individual lines
_TRAILING = re.compile(r"\s*//\s*indirect\s*$|\s*//.*$|,\s*$")


def _clean(line: str) -> str:
    """Strip trailing comments and punctuation from a dependency line."""
    return _TRAILING.sub("", line).strip()


def _is_meaningful(line: str) -> bool:
    return bool(line) and not _NOISE.match(line)


def extract_dep_changes(diff_file: DiffFile) -> list[FlagReason]:
    """
    Return FlagReasons describing each individual dependency added or removed.

    Works generically across requirements.txt, go.mod, package.json,
    Cargo.toml, and similar formats by filtering structural noise and
    returning the cleaned content of every added/removed line.

    pyproject.toml receives stricter filtering: only PEP 508 quoted specs and
    poetry-style versioned deps are shown; tool config and metadata are skipped.
    """
    filename = (diff_file.new_path or "").split("/")[-1]
    is_pyproject = filename == "pyproject.toml"

    reasons: list[FlagReason] = []

    for raw in diff_file.added_lines:
        cleaned = _clean(raw)
        if is_pyproject:
            if _is_pyproject_dep(cleaned):
                reasons.append(FlagReason(source="content", description=f"{cleaned}  — added"))
        elif _is_meaningful(cleaned):
            reasons.append(FlagReason(source="content", description=f"{cleaned}  — added"))

    for raw in diff_file.removed_lines:
        cleaned = _clean(raw)
        if is_pyproject:
            if _is_pyproject_dep(cleaned):
                reasons.append(FlagReason(source="content", description=f"{cleaned}  — removed"))
        elif _is_meaningful(cleaned):
            reasons.append(FlagReason(source="content", description=f"{cleaned}  — removed"))

    return reasons
