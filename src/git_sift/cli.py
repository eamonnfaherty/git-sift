"""Click CLI entry point for git-sift."""
from __future__ import annotations

import sys

import click

from git_sift.models import CATEGORY_ALIASES, DiffMode, DiffOptions, RiskCategory
from git_sift.wizard import run_check, run_summarize, run_wizard


def _parse_fail_on(value: str) -> set[RiskCategory]:
    """Parse a comma-separated --fail-on string into a set of RiskCategory values.

    Accepts category names (case-insensitive) or numeric risk levels (1–10).
    Raises click.BadParameter on unknown tokens.
    """
    categories: set[RiskCategory] = set()
    for token in value.split(","):
        token = token.strip().lower()
        if not token:
            continue
        if token.isdigit():
            level = int(token)
            try:
                categories.add(RiskCategory(level))
            except ValueError:
                valid_levels = ", ".join(str(c.value) for c in RiskCategory)
                raise click.BadParameter(
                    f"unknown risk level {level!r}. Valid levels: {valid_levels}"
                )
        elif token in CATEGORY_ALIASES:
            categories.add(CATEGORY_ALIASES[token])
        else:
            valid_names = ", ".join(sorted(CATEGORY_ALIASES))
            raise click.BadParameter(
                f"unknown category {token!r}.\n"
                f"Valid names: {valid_names}\n"
                f"Or use a numeric risk level 1–10."
            )
    return categories


@click.command()
@click.option("--staged", "mode", flag_value="staged", help="Review staged changes (git diff --cached).")
@click.option("--unstaged", "mode", flag_value="unstaged", help="Review unstaged working-tree changes.")
@click.option("--ref-a", default=None, metavar="REF",
              help="Base ref for comparison (default: main/master).")
@click.option("--ref-b", default=None, metavar="REF",
              help="Head ref for comparison (default: HEAD).")
@click.option(
    "--fail-on",
    default=None,
    metavar="CATEGORIES",
    help=(
        "Non-interactive mode: exit 1 if any changed files fall into the given "
        "risk categories. Accepts a comma-separated list of names or risk levels, e.g. "
        "--fail-on security,dependency  or  --fail-on 1,2"
    ),
)
@click.option(
    "--install-skill",
    is_flag=True,
    default=False,
    help="Install the /git-sift Claude Code skill to ~/.claude/commands/ and exit.",
)
@click.option(
    "--summarize",
    is_flag=True,
    default=False,
    help="Print a count of changed files per risk category and exit. No prompts.",
)
@click.option(
    "--clear-session",
    is_flag=True,
    default=False,
    help="Delete the saved review session for this repository and exit.",
)
@click.option(
    "--menu",
    "menu_mode",
    is_flag=True,
    default=False,
    help="Start the review with the category selection menu instead of walking categories sequentially.",
)
def main(
    mode: str | None,
    ref_a: str | None,
    ref_b: str | None,
    fail_on: str | None,
    install_skill: bool,
    summarize: bool,
    clear_session: bool,
    menu_mode: bool,
) -> None:
    """
    Interactive wizard for reviewing AI-generated code changes by risk level.

    By default (no flags), compares the current branch against main.
    Walk through each changed file from highest to lowest risk.

    Pass --fail-on to run non-interactively and exit 1 if matching files are found.
    Pass --summarize to print category counts and exit.
    Pass --install-skill to install the /git-sift Claude Code skill and exit.
    """
    if clear_session:
        from git_sift.session import clear_session as _clear, session_path
        path = session_path()
        _clear()
        if path and not path.exists():
            click.echo(f"Session cleared: {path}")
        else:
            click.echo("No session file found.")
        sys.exit(0)

    if install_skill:
        from git_sift.skill import install_skill as _install
        already_existed, dest = _install()
        if already_existed:
            click.echo(f"Updated skill: {dest}")
        else:
            click.echo(f"Installed skill: {dest}")
        click.echo("Type /git-sift inside any Claude Code session to use it.")
        sys.exit(0)
    options: DiffOptions | None = None

    if mode == "staged":
        options = DiffOptions(mode=DiffMode.STAGED)
    elif mode == "unstaged":
        options = DiffOptions(mode=DiffMode.UNSTAGED)
    elif ref_a is not None or ref_b is not None:
        options = DiffOptions(mode=DiffMode.REFS, ref_a=ref_a, ref_b=ref_b)
    else:
        from git_sift.git import get_current_branch, get_default_base
        current = get_current_branch()
        base = get_default_base()
        if current and current != base:
            options = DiffOptions(mode=DiffMode.REFS, ref_a=base, ref_b=current)

    if summarize:
        if options is None:
            from git_sift.git import get_current_branch, get_default_base
            options = DiffOptions(
                mode=DiffMode.REFS,
                ref_a=get_default_base(),
                ref_b=get_current_branch() or "HEAD",
            )
        code = run_summarize(options)
        sys.exit(code)

    if fail_on is not None:
        categories = _parse_fail_on(fail_on)
        if not categories:
            raise click.BadParameter("--fail-on requires at least one category.")
        if options is None:
            # No explicit diff source — default to branch-vs-main non-interactively
            from git_sift.git import get_current_branch, get_default_base
            options = DiffOptions(
                mode=DiffMode.REFS,
                ref_a=get_default_base(),
                ref_b=get_current_branch() or "HEAD",
            )
        code = run_check(options, categories)
    else:
        code = run_wizard(options=options, menu_mode=menu_mode)

    sys.exit(code)
