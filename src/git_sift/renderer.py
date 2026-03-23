"""Rich-based display utilities."""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from git_sift.models import (
    CATEGORY_COLORS,
    CATEGORY_LABELS,
    DiffFile,
    FileReview,
    ReviewDecision,
    RiskCategory,
)

_REASON_COLORS = {
    RiskCategory.SECURITY: "bold red",
    RiskCategory.DEPENDENCIES: "red",
    RiskCategory.INFRASTRUCTURE: "dark_orange",
    RiskCategory.DATABASE_MIGRATIONS: "orange1",
    RiskCategory.ARCH_TESTS: "yellow",
    RiskCategory.EXISTING_TESTS: "yellow",
    RiskCategory.EXISTING_CODE: "green",
    RiskCategory.NEW_CODE: "cyan",
    RiskCategory.CONFIG_ENV: "blue",
    RiskCategory.DOCS_FORMATTING: "bright_black",
}

console = Console()


def print_categorization_table(reviews: list[FileReview]) -> None:
    """Print a summary table of files grouped by category."""
    counts: dict[RiskCategory, int] = {}
    for r in reviews:
        counts[r.category] = counts.get(r.category, 0) + 1

    table = Table(title="Files by Risk Category", show_header=True, header_style="bold")
    table.add_column("Risk", style="bold", no_wrap=True)
    table.add_column("Category", no_wrap=True)
    table.add_column("Files", justify="right")

    for cat in sorted(counts.keys()):
        color = CATEGORY_COLORS.get(cat, "white")
        label = CATEGORY_LABELS.get(cat, str(cat))
        table.add_row(
            f"[{color}]{cat.value}[/{color}]",
            f"[{color}]{label}[/{color}]",
            str(counts[cat]),
        )

    console.print()
    console.print(table)
    console.print()


def print_category_header(category: RiskCategory, index: int, total: int) -> None:
    color = CATEGORY_COLORS.get(category, "white")
    label = CATEGORY_LABELS.get(category, str(category))
    console.rule(
        f"[{color}]Category {index}/{total}: {label} (Risk {category.value})[/{color}]"
    )


def print_file_diff(diff_file: DiffFile, index: int, total: int) -> None:
    """Render the diff for a single file using Rich syntax highlighting."""
    console.print()
    console.print(
        f"  [bold]File {index}/{total}:[/bold] [cyan]{diff_file.display_path}[/cyan]"
    )
    if diff_file.raw_diff.strip():
        syntax = Syntax(
            diff_file.raw_diff,
            "diff",
            theme="ansi_dark",
            line_numbers=False,
            word_wrap=True,
        )
        console.print(Panel(syntax, border_style="dim"))
    else:
        console.print("  [dim](no textual diff — binary or metadata-only change)[/dim]")
    console.print()


def print_help() -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold cyan")
    table.add_column("Action")
    table.add_row("A", "Approve — looks good")
    table.add_row("C", "Concern — worth noting but not blocking")
    table.add_row("B", "Blocker — must be fixed before merge")
    table.add_row("S", "Skip — review later / not applicable")
    table.add_row("M", "Menu — jump to category selection menu")
    table.add_row("Q", "Quit — exit the review session")
    table.add_row("?", "Show this help")
    console.print(Panel(table, title="Review Options", border_style="cyan"))


def print_summary_table(reviews: list[FileReview]) -> None:
    """Print the end-of-session summary."""
    table = Table(title="Review Summary", show_header=True, header_style="bold")
    table.add_column("Category")
    table.add_column("Approved", justify="right")
    table.add_column("Concerns", justify="right")
    table.add_column("Blockers", justify="right")
    table.add_column("Skipped", justify="right")

    from collections import defaultdict
    data: dict[RiskCategory, dict[str, int]] = defaultdict(
        lambda: {"approve": 0, "concern": 0, "blocker": 0, "skip": 0, "none": 0}
    )

    for r in reviews:
        key = r.decision.value if r.decision else "none"
        data[r.category][key] += 1

    for cat in sorted(data.keys()):
        color = CATEGORY_COLORS.get(cat, "white")
        label = CATEGORY_LABELS.get(cat, str(cat))
        d = data[cat]
        table.add_row(
            f"[{color}]{label}[/{color}]",
            str(d["approve"]),
            str(d["concern"]),
            str(d["blocker"]),
            str(d["skip"] + d["none"]),
        )

    console.print()
    console.print(table)


def print_file_context_bar(review: FileReview, index: int, total: int) -> None:
    """Print a compact status bar pinned just above the prompt.

    Repeats the file path and category so the reviewer always has context
    at the bottom of the screen regardless of diff length.
    """
    color = CATEGORY_COLORS.get(review.category, "white")
    label = CATEGORY_LABELS.get(review.category, str(review.category))
    console.rule(
        f"[bold]File {index}/{total}[/bold]  "
        f"[cyan]{review.diff_file.display_path}[/cyan]  "
        f"[{color}]{label} · Risk {review.category.value}[/{color}]"
    )


def print_session_resume(
    carried: list[FileReview],
    changed: list[FileReview],
    fresh: list[FileReview],
) -> None:
    """Print a resume banner and decision summary when a previous session is restored."""
    total = len(carried) + len(changed) + len(fresh)

    # Banner
    console.rule("[bold cyan]Resuming session[/bold cyan]")
    console.print(
        f"  [dim]{len(carried)} decision(s) carried forward"
        + (f"  ·  [bold yellow]{len(changed)} file(s) changed — needs re-review[/bold yellow]" if changed else "")
        + (f"  ·  {len(fresh)} new file(s)" if fresh else "")
        + f"  ·  {total} total[/dim]"
    )
    console.print()

    # Decision summary table
    if not carried:
        return

    _DECISION_STYLE = {
        ReviewDecision.APPROVE:  ("[bold green]✓ Approved[/bold green]",  "approve"),
        ReviewDecision.CONCERN:  ("[yellow]! Concern[/yellow]",            "concern"),
        ReviewDecision.BLOCKER:  ("[bold red]✗ Blocker[/bold red]",        "blocker"),
        ReviewDecision.SKIP:     ("[dim]⊘ Skipped[/dim]",                  "skip"),
    }

    table = Table(show_header=True, header_style="bold", title="Carried-forward decisions")
    table.add_column("Decision", no_wrap=True)
    table.add_column("Category", no_wrap=True)
    table.add_column("File")

    for review in sorted(carried, key=lambda r: (r.category, r.diff_file.display_path)):
        if review.decision is None:
            continue
        badge, _ = _DECISION_STYLE.get(review.decision, (str(review.decision), ""))
        color = CATEGORY_COLORS.get(review.category, "white")
        label = CATEGORY_LABELS.get(review.category, str(review.category))
        note_suffix = f"  [dim]{review.note}[/dim]" if review.note else ""
        table.add_row(
            badge,
            f"[{color}]{label}[/{color}]",
            f"{review.diff_file.display_path}{note_suffix}",
        )

    console.print(table)

    if changed:
        console.print()
        console.print("[bold yellow]Files that changed since last review:[/bold yellow]")
        for r in changed:
            color = CATEGORY_COLORS.get(r.category, "white")
            console.print(f"  [bold yellow]↺[/bold yellow]  [{color}]{r.diff_file.display_path}[/{color}]")

    console.print()


def print_flag_reasons(review: FileReview) -> None:
    """Print the 'Why this was flagged' panel for a review (used in wizard and browser)."""
    if not review.reasons:
        return
    reason_color = _REASON_COLORS.get(review.category, "yellow")
    lines = [f"  • {r.description}" for r in review.reasons]
    console.print(
        Panel(
            "\n".join(lines),
            title="[bold]Why this was flagged[/bold]",
            border_style=reason_color,
            expand=False,
        )
    )


def print_browser_file_header(review: FileReview, index: int, total: int) -> None:
    """Display the file header for the interactive browser, including flag reasons."""
    color = CATEGORY_COLORS.get(review.category, "white")
    label = CATEGORY_LABELS.get(review.category, str(review.category))

    console.print()
    console.rule(
        f"[{color}]File {index}/{total}: {review.diff_file.display_path}  "
        f"[{color}]{label} (Risk {review.category.value})[/{color}]"
    )

    # Show existing wizard decision if present
    if review.decision is not None:
        decision_badge = {
            "approve": "[bold green]✓ APPROVED[/bold green]",
            "concern": "[bold yellow]! CONCERN[/bold yellow]",
            "blocker": "[bold red]✗ BLOCKER[/bold red]",
            "skip": "[dim]⊘ SKIPPED[/dim]",
        }.get(review.decision.value, f"[dim]{review.decision.value}[/dim]")
        note_str = f"  — {review.note}" if review.note else ""
        console.print(f"  Wizard decision: {decision_badge}{note_str}")

    # Flag reasons panel
    print_flag_reasons(review)


def print_category_menu(reviews: list[FileReview]) -> None:
    """Print the category selection menu showing pending/done counts per category."""
    from collections import Counter
    total_by_cat: Counter[RiskCategory] = Counter(r.category for r in reviews)
    done_by_cat: Counter[RiskCategory] = Counter(
        r.category for r in reviews if r.decision is not None
    )

    console.print()
    console.rule("[bold cyan]Category Menu[/bold cyan]")
    table = Table(show_header=True, header_style="bold")
    table.add_column("#", justify="right", no_wrap=True)
    table.add_column("Risk", justify="right", no_wrap=True)
    table.add_column("Category", no_wrap=True)
    table.add_column("Files", justify="right")
    table.add_column("Done", justify="right")
    table.add_column("Pending", justify="right")

    for i, cat in enumerate(sorted(total_by_cat.keys()), start=1):
        color = CATEGORY_COLORS.get(cat, "white")
        label = CATEGORY_LABELS.get(cat, str(cat))
        total = total_by_cat[cat]
        done = done_by_cat[cat]
        pending = total - done
        pending_str = f"[bold]{pending}[/bold]" if pending else "[dim]0[/dim]"
        table.add_row(
            str(i),
            f"[{color}]{cat.value}[/{color}]",
            f"[{color}]{label}[/{color}]",
            str(total),
            str(done),
            pending_str,
        )

    console.print(table)
    console.print("  [dim]Enter a number to review that category, or [bold]Q[/bold] to quit.[/dim]")
    console.print()


def print_browser_help() -> None:
    """Display help for the interactive file browser."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold cyan")
    table.add_column("Action")
    table.add_row("A", "Approve — this file looks good")
    table.add_row("R", "Recommend change — ask Claude to fix it")
    table.add_row("S", "Skip — come back later")
    table.add_row("N", "Next file")
    table.add_row("P", "Previous file")
    table.add_row("?", "Show this help")
    console.print(Panel(table, title="Browser Options", border_style="cyan"))


def print_blockers_and_concerns(reviews: list[FileReview]) -> None:
    blockers = [r for r in reviews if r.decision == ReviewDecision.BLOCKER]
    concerns = [r for r in reviews if r.decision == ReviewDecision.CONCERN]

    if blockers:
        console.print()
        console.print("[bold red]Blockers:[/bold red]")
        for r in blockers:
            note = f" — {r.note}" if r.note else ""
            console.print(f"  [red]✗[/red] {r.diff_file.display_path}{note}")

    if concerns:
        console.print()
        console.print("[bold yellow]Concerns:[/bold yellow]")
        for r in concerns:
            note = f" — {r.note}" if r.note else ""
            console.print(f"  [yellow]![/yellow] {r.diff_file.display_path}{note}")
