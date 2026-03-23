"""Interactive file browser with Claude-assisted fix support."""
from __future__ import annotations

from rich.prompt import Prompt

from git_sift.claude_runner import check_claude_available, run_claude
from git_sift.models import (
    CATEGORY_LABELS,
    BrowserResult,
    DiffOptions,
    FileReview,
    RiskCategory,
)
from git_sift.renderer import (
    console,
    print_browser_file_header,
    print_browser_help,
    print_file_diff,
)


def _build_claude_prompt(review: FileReview, recommendation: str) -> str:
    """Build the prompt to pass to Claude Code for fixing the file."""
    category = review.category
    label = CATEGORY_LABELS.get(category, str(category))
    value = category.value

    security_instruction = ""
    if category == RiskCategory.SECURITY:
        security_instruction = (
            "3. If the risk category is SECURITY, also add:\n"
            "   # AI-REVIEW-FIX(SECURITY): <vulnerability this addresses>\n"
        )
        next_step = "4."
    else:
        next_step = "3."

    return (
        f"You are fixing an issue found during a code review of AI-generated changes.\n\n"
        f"File: {review.diff_file.display_path}\n"
        f"Risk category: {label} (level {value}/10 — 1 = highest risk)\n\n"
        f"Reviewer's recommendation:\n{recommendation}\n\n"
        f"Diff for context:\n{review.diff_file.raw_diff}\n\n"
        f"Instructions:\n"
        f"1. Make exactly the fix described by the reviewer — keep changes minimal.\n"
        f"2. On every line you add or modify, add an inline comment:\n"
        f"   # AI-REVIEW-FIX: <brief explanation of what changed and why>\n"
        f"{security_instruction}"
        f"{next_step} Do not remove existing comments or unrelated code.\n"
    )


def run_browser(reviews: list[FileReview], options: DiffOptions) -> BrowserResult:
    """
    Run the interactive file browser over all reviewed files.

    Returns BrowserResult indicating whether Claude made changes (triggering a
    wizard restart) or all files were approved.
    """
    if not reviews:
        return BrowserResult(all_approved=True, recommendations_made=False)

    approved: set[int] = set()
    index = 0

    console.print()
    console.print(
        "[bold]Interactive File Browser[/bold]  "
        f"[dim]{len(reviews)} file(s) to review[/dim]"
    )
    console.print("[dim]Press ? for help[/dim]")

    while True:
        review = reviews[index]
        total = len(reviews)

        print_browser_file_header(review, index + 1, total)
        print_file_diff(review.diff_file, index + 1, total)

        # Show approval status
        status = "[bold green]✓ approved[/bold green]" if index in approved else "[dim]pending[/dim]"
        console.print(f"  Status: {status}")

        answer = Prompt.ask(
            "  [bold][A]pprove[/bold]  [yellow][R]ecommend change[/yellow]"
            "  [dim][S]kip[/dim]  [cyan][N]ext[/cyan]  [magenta][P]rev[/magenta]  [cyan][?]Help[/cyan]",
            default="N",
            console=console,
        ).strip().lower()

        if answer == "?":
            print_browser_help()
            continue

        elif answer == "a":
            approved.add(index)
            console.print(f"  [bold green]✓ Approved[/bold green]: {review.diff_file.display_path}")
            index = (index + 1) % total

        elif answer == "r":
            if not check_claude_available():
                console.print(
                    "[bold red]claude CLI not found.[/bold red] "
                    "Install Claude Code and ensure `claude` is on your PATH."
                )
                continue

            recommendation = Prompt.ask(
                "  [yellow]Describe the change needed[/yellow]",
                console=console,
            ).strip()
            if not recommendation:
                console.print("[dim]No recommendation entered — staying on this file.[/dim]")
                continue

            prompt = _build_claude_prompt(review, recommendation)
            console.print("[bold yellow]Launching Claude Code session…[/bold yellow]")
            run_claude(prompt)

            # Any Claude session = changes may have been made → restart wizard
            return BrowserResult(all_approved=False, recommendations_made=True)

        elif answer == "s":
            console.print(f"  [dim]Skipped[/dim]: {review.diff_file.display_path}")
            index = (index + 1) % total

        elif answer in ("n", ""):
            index = (index + 1) % total

        elif answer == "p":
            index = (index - 1) % total

        else:
            console.print("[red]Invalid choice. Enter A, R, S, N, P, or ?[/red]")
            continue

        # Check if all files are approved after every navigation step
        if len(approved) == total:
            console.print("\n[bold green]All files approved.[/bold green]")
            return BrowserResult(all_approved=True, recommendations_made=False)

        # Check if we've come full circle with no more pending approvals needed
        # (user has visited every file and made decisions; stop when wrap-around detected)
        # We rely on the explicit "all approved" check above; keep looping otherwise.
