"""Tests for the unified diff parser."""
import textwrap

from git_sift.parser import parse_diff


SIMPLE_DIFF = textwrap.dedent("""\
    diff --git a/src/foo.py b/src/foo.py
    index abc1234..def5678 100644
    --- a/src/foo.py
    +++ b/src/foo.py
    @@ -1,4 +1,5 @@
     def hello():
    -    print("hello")
    +    print("hello world")
    +    return True
""")

NEW_FILE_DIFF = textwrap.dedent("""\
    diff --git a/new_module.py b/new_module.py
    new file mode 100644
    index 0000000..1234567
    --- /dev/null
    +++ b/new_module.py
    @@ -0,0 +1,3 @@
    +def add(a, b):
    +    return a + b
    +
""")

DELETED_FILE_DIFF = textwrap.dedent("""\
    diff --git a/old_module.py b/old_module.py
    deleted file mode 100644
    index 1234567..0000000
    --- a/old_module.py
    +++ /dev/null
    @@ -1,3 +0,0 @@
    -def old():
    -    pass
    -
""")

RENAME_DIFF = textwrap.dedent("""\
    diff --git a/old_name.py b/new_name.py
    rename from old_name.py
    rename to new_name.py
""")


def test_parse_simple_modification():
    files = parse_diff(SIMPLE_DIFF)
    assert len(files) == 1
    f = files[0]
    assert f.old_path == "src/foo.py"
    assert f.new_path == "src/foo.py"
    assert not f.is_new_file
    assert not f.is_deleted
    assert not f.is_rename
    assert len(f.hunks) == 1
    hunk = f.hunks[0]
    assert hunk.old_start == 1
    assert hunk.new_start == 1


def test_parse_added_removed_lines():
    files = parse_diff(SIMPLE_DIFF)
    f = files[0]
    assert '    print("hello world")' in f.added_lines
    assert '    return True' in f.added_lines
    assert '    print("hello")' in f.removed_lines


def test_parse_new_file():
    files = parse_diff(NEW_FILE_DIFF)
    assert len(files) == 1
    f = files[0]
    assert f.is_new_file
    assert not f.is_deleted
    assert f.new_path == "new_module.py"
    assert "def add(a, b):" in f.added_lines


def test_parse_deleted_file():
    files = parse_diff(DELETED_FILE_DIFF)
    assert len(files) == 1
    f = files[0]
    assert f.is_deleted
    assert not f.is_new_file
    assert f.old_path == "old_module.py"
    assert "def old():" in f.removed_lines


def test_parse_rename():
    files = parse_diff(RENAME_DIFF)
    assert len(files) == 1
    f = files[0]
    assert f.is_rename
    assert f.old_path == "old_name.py"
    assert f.new_path == "new_name.py"
    assert f.display_path == "old_name.py -> new_name.py"


def test_parse_empty_diff():
    files = parse_diff("")
    assert files == []


def test_parse_multiple_files():
    multi = SIMPLE_DIFF + "\n" + NEW_FILE_DIFF
    files = parse_diff(multi)
    assert len(files) == 2
