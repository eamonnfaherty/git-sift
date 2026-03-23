"""Tests for the Claude Code skill installer."""
from pathlib import Path
from unittest.mock import patch

from git_sift.skill import SKILL_CONTENT, SKILL_FILENAME, install_skill, skill_install_path


def test_skill_install_path():
    path = skill_install_path()
    assert path.name == SKILL_FILENAME
    assert ".claude" in path.parts
    assert "commands" in path.parts


def test_install_skill_writes_file(tmp_path):
    dest = tmp_path / ".claude" / "commands" / SKILL_FILENAME
    with patch("git_sift.skill.skill_install_path", return_value=dest):
        already_existed, returned_path = install_skill()
    assert not already_existed
    assert returned_path == dest
    assert dest.exists()
    assert dest.read_text(encoding="utf-8") == SKILL_CONTENT


def test_install_skill_overwrites_existing(tmp_path):
    dest = tmp_path / ".claude" / "commands" / SKILL_FILENAME
    dest.parent.mkdir(parents=True)
    dest.write_text("old content", encoding="utf-8")
    with patch("git_sift.skill.skill_install_path", return_value=dest):
        already_existed, _ = install_skill()
    assert already_existed
    assert dest.read_text(encoding="utf-8") == SKILL_CONTENT


def test_skill_content_contains_key_sections():
    assert "/git-sift" in SKILL_CONTENT
    assert "git-sift" in SKILL_CONTENT
    assert "--fail-on" in SKILL_CONTENT
    assert "Risk" in SKILL_CONTENT
    assert "Security" in SKILL_CONTENT
