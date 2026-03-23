"""Parse unified diff text into DiffFile objects."""
from __future__ import annotations

import re
from typing import Optional

from git_sift.models import DiffFile, DiffHunk

_DIFF_HEADER = re.compile(r"^diff --git a/(.+) b/(.+)$")
_HUNK_HEADER = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@"
)


def parse_diff(raw: str) -> list[DiffFile]:
    """Parse a unified diff string into a list of DiffFile objects."""
    files: list[DiffFile] = []
    current_file: Optional[DiffFile] = None
    current_hunk: Optional[DiffHunk] = None
    current_raw_lines: list[str] = []

    lines = raw.splitlines(keepends=True)

    def flush_hunk() -> None:
        nonlocal current_hunk
        if current_hunk is not None and current_file is not None:
            current_file.hunks.append(current_hunk)
            current_hunk = None

    def flush_file() -> None:
        nonlocal current_file, current_raw_lines
        flush_hunk()
        if current_file is not None:
            current_file.raw_diff = "".join(current_raw_lines)
            files.append(current_file)
            current_file = None
            current_raw_lines = []

    for line in lines:
        stripped = line.rstrip("\n")

        m = _DIFF_HEADER.match(stripped)
        if m:
            flush_file()
            old_path = m.group(1)
            new_path = m.group(2)
            current_file = DiffFile(old_path=old_path, new_path=new_path)
            current_raw_lines = [line]
            continue

        if current_file is None:
            continue

        current_raw_lines.append(line)

        if stripped.startswith("new file mode"):
            current_file.is_new_file = True
            continue

        if stripped.startswith("deleted file mode"):
            current_file.is_deleted = True
            continue

        if stripped.startswith("rename from "):
            current_file.is_rename = True
            current_file.old_path = stripped[len("rename from "):]
            continue

        if stripped.startswith("rename to "):
            current_file.new_path = stripped[len("rename to "):]
            continue

        # Skip index/--- /+++ lines — they're metadata
        if (stripped.startswith("index ")
                or stripped.startswith("--- ")
                or stripped.startswith("+++ ")
                or stripped.startswith("Binary files")):
            continue

        m = _HUNK_HEADER.match(stripped)
        if m:
            flush_hunk()
            old_start = int(m.group(1))
            old_count = int(m.group(2)) if m.group(2) is not None else 1
            new_start = int(m.group(3))
            new_count = int(m.group(4)) if m.group(4) is not None else 1
            current_hunk = DiffHunk(
                old_start=old_start,
                old_count=old_count,
                new_start=new_start,
                new_count=new_count,
            )
            continue

        if current_hunk is not None:
            if stripped.startswith(("+", "-", " ")):
                current_hunk.lines.append(stripped)

    flush_file()
    return files
