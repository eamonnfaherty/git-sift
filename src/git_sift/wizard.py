"""Orchestrates the interactive review wizard."""
from __future__ import annotations

from typing import Optional

from rich.prompt import Prompt

from git_sift.categorizer import categorize_all
from git_sift.git import assert_in_git_repo, fetch_diff, get_current_branch, get_default_base
from git_sift.models import (
    CATEGORY_COLORS,
    CATEGORY_LABELS,
    DiffMode,
    DiffOptions,
    ReviewDecision,
    RiskCategory,
)
from git_sift.parser import parse_diff
from git_sift.renderer import (
    console,
    print_blockers_and_concerns,
    print_categorization_table,
    print_category_header,
    print_category_menu,
    print_file_context_bar,
    print_file_diff,
    print_flag_reasons,
    print_help,
    print_session_resume,
    print_summary_table,
)
from git_sift.session import RestoreResult, clear_session, load_session, restore_decisions, save_session
from git_sift.summary import build_summary, exit_code

_DECISION_MAP = {
    "a": ReviewDecision.APPROVE,
    "c": ReviewDecision.CONCERN,
    "b": ReviewDecision.BLOCKER,
    "s": ReviewDecision.SKIP,
    "m": ReviewDecision.MENU,
}


def _prompt_decision(_diff_path: str) -> tuple[ReviewDecision, Optional[str]]:
    """Interactively prompt for a review decision, returning (decision, note)."""
    while True:
        answer = Prompt.ask(
            f"  [bold][A]pprove[/bold] [yellow][C]oncern[/yellow] "
            f"[red][B]locker[/red] [dim][S]kip[/dim] [cyan][M]enu[/cyan] "
            f"[cyan][?]Help[/cyan] [dim][Q]uit[/dim]",
            default="A",
            console=console,
        ).strip().lower()

        if answer == "?":
            print_help()
            continue

        if answer == "q":
            console.print("[dim]Quitting review.[/dim]")
            raise SystemExit(0)

        decision = _DECISION_MAP.get(answer)
        if decision is None:
            console.print("[red]Invalid choice. Enter A, C, B, S, M, Q, or ?[/red]")
            continue

        if decision == ReviewDecision.MENU:
            return decision, None

        note: Optional[str] = None
        if decision in (ReviewDecision.CONCERN, ReviewDecision.BLOCKER):
            note_input = Prompt.ask(
                "  [dim]Optional note (press Enter to skip)[/dim]",
                default="",
                console=console,
            ).strip()
            note = note_input if note_input else None

        return decision, note


def _select_mode_interactively() -> DiffOptions:
    """Ask the user which diff mode to use."""
    console.print()
    console.print("[bold]Select diff source:[/bold]")
    console.print("  [cyan]1[/cyan]  Branch vs main (current branch → main)  [dim](default)[/dim]")
    console.print("  [cyan]2[/cyan]  Staged changes")
    console.print("  [cyan]3[/cyan]  Unstaged changes")
    console.print("  [cyan]4[/cyan]  Custom ref range")
    console.print()

    choice = Prompt.ask("Choice", default="1", console=console).strip()

    if choice == "1":
        base = get_default_base()
        current = get_current_branch() or "HEAD"
        console.print(f"  [dim]Comparing [cyan]{current}[/cyan] → [cyan]{base}[/cyan][/dim]")
        return DiffOptions(mode=DiffMode.REFS, ref_a=base, ref_b=current)
    elif choice == "2":
        return DiffOptions(mode=DiffMode.STAGED)
    elif choice == "3":
        return DiffOptions(mode=DiffMode.UNSTAGED)
    elif choice == "4":
        ref_a = Prompt.ask("  ref_a (base)", console=console).strip()
        ref_b = Prompt.ask("  ref_b (head, default HEAD)", default="HEAD", console=console).strip()
        return DiffOptions(mode=DiffMode.REFS, ref_a=ref_a, ref_b=ref_b)
    else:
        console.print("[red]Invalid choice, defaulting to branch vs main.[/red]")
        base = get_default_base()
        current = get_current_branch() or "HEAD"
        return DiffOptions(mode=DiffMode.REFS, ref_a=base, ref_b=current)


def _select_category_from_menu(
    reviews: list, categories_present: list[RiskCategory]
) -> Optional[RiskCategory]:
    """Show the category menu and return the selected category, or None if the user quits."""
    print_category_menu(reviews)
    index_map = {str(i): cat for i, cat in enumerate(categories_present, start=1)}

    while True:
        answer = Prompt.ask(
            "  Select category number (or [bold]Q[/bold] to quit)",
            console=console,
        ).strip().lower()

        if answer == "q":
            console.print("[dim]Quitting review.[/dim]")
            raise SystemExit(0)

        if answer in index_map:
            return index_map[answer]

        console.print(
            f"[red]Invalid choice. Enter a number 1–{len(index_map)} or Q.[/red]"
        )


def _review_single_category(
    category: RiskCategory,
    cat_index: int,
    total_cats: int,
    reviews: list,
    options: "DiffOptions",
    changed_paths: set[str],
) -> bool:
    """
    Review all pending files in *category*.

    Returns True if the user pressed M (wants to go back to the menu),
    False when the category is fully reviewed.
    """
    cat_files = [r for r in reviews if r.category == category]
    print_category_header(category, cat_index, total_cats)

    for file_index, review in enumerate(cat_files, start=1):
        path = review.diff_file.display_path

        # Carried forward — show a compact one-liner, skip prompting
        if review.decision is not None and review.decision != ReviewDecision.MENU and path not in changed_paths:
            color = CATEGORY_COLORS.get(review.category, "white")
            badge = {
                "approve": "[bold green]✓ carried[/bold green]",
                "concern": "[yellow]! carried[/yellow]",
                "blocker": "[bold red]✗ carried[/bold red]",
                "skip":    "[dim]⊘ carried[/dim]",
            }.get(review.decision.value, "[dim]carried[/dim]")
            note_str = f"  [dim]{review.note}[/dim]" if review.note else ""
            console.print(
                f"  {badge}  [{color}]{review.diff_file.display_path}[/{color}]{note_str}"
            )
            continue

        # Changed since last review — flag it
        if path in changed_paths:
            console.print(
                f"  [bold yellow]↺ CHANGED — re-review[/bold yellow]"
                f"  [dim]{path}[/dim]"
            )

        print_file_diff(review.diff_file, file_index, len(cat_files))
        print_flag_reasons(review)
        print_file_context_bar(review, file_index, len(cat_files))
        decision, note = _prompt_decision(review.diff_file.display_path)

        if decision == ReviewDecision.MENU:
            return True  # caller should show menu

        review.decision = decision
        review.note = note
        save_session(options, reviews)

    return False  # category completed normally


def run_wizard(options: Optional[DiffOptions] = None, menu_mode: bool = False) -> int:
    """
    Main wizard entry point.
    Returns an exit code: 0 (clean), 1 (blockers), 2 (error).
    """
    assert_in_git_repo()

    if options is None:
        options = _select_mode_interactively()

    console.print()
    with console.status("[bold green]Running git diff…[/bold green]"):
        raw_diff = fetch_diff(options)

    if not raw_diff.strip():
        console.print("[yellow]No differences found.[/yellow]")
        clear_session()   # diff is gone — session is stale
        return 0

    with console.status("[bold green]Parsing and categorizing…[/bold green]"):
        diff_files = parse_diff(raw_diff)
        reviews = categorize_all(diff_files)

    if not reviews:
        console.print("[yellow]No files to review.[/yellow]")
        return 0

    # Restore decisions from a previous session
    saved = load_session(options)
    restore = restore_decisions(reviews, saved)

    carried = restore.total_carried
    changed_paths = {r.diff_file.display_path for r in restore.changed}

    console.print(f"\n[bold]Found {len(reviews)} changed file(s).[/bold]")

    if carried:
        print_session_resume(restore.carried, restore.changed, restore.fresh)

    print_categorization_table(reviews)

    # Walk categories from highest to lowest risk
    categories_present = sorted(set(r.category for r in reviews))
    total_cats = len(categories_present)

    def _has_pending(cat: RiskCategory) -> bool:
        for r in reviews:
            if r.category != cat:
                continue
            if r.diff_file.display_path in changed_paths:
                return True
            if r.decision is None or r.decision == ReviewDecision.MENU:
                return True
        return False

    def _run_menu_loop() -> None:
        while any(_has_pending(c) for c in categories_present):
            category = _select_category_from_menu(reviews, categories_present)
            cat_index = categories_present.index(category) + 1
            _review_single_category(
                category, cat_index, total_cats, reviews, options, changed_paths
            )
            console.print()

    if menu_mode:
        _run_menu_loop()
    else:
        # Sequential mode: walk categories in order; M key switches to menu
        switched_to_menu = False
        for cat_index, category in enumerate(categories_present, start=1):
            if switched_to_menu:
                break
            want_menu = _review_single_category(
                category, cat_index, total_cats, reviews, options, changed_paths
            )
            console.print()
            if want_menu:
                switched_to_menu = True

        if switched_to_menu:
            _run_menu_loop()

    # Summary
    summary = build_summary(reviews)
    print_summary_table(reviews)
    print_blockers_and_concerns(reviews)

    code = exit_code(summary)
    if code == 0:
        console.print("\n[bold green]Review complete — no blockers.[/bold green]")
    else:
        console.print(f"\n[bold red]Review complete — {len(summary.blockers)} blocker(s) found.[/bold red]")

    # Browser loop — restarts full wizard if Claude makes changes
    from git_sift.browser import run_browser
    from git_sift.merger import prompt_and_merge

    while True:
        result = run_browser(reviews, options)
        if result.recommendations_made:
            console.print("[bold yellow]Changes made — restarting full review…[/bold yellow]")
            return run_wizard(options, menu_mode=menu_mode)
        break  # no recommendations → proceed to merge prompt

    answer = Prompt.ask(
        "[bold]Merge this branch via PR?[/bold] [Y/n]",
        default="Y",
        console=console,
    )
    if answer.strip().lower() in ("y", ""):
        merge_code = prompt_and_merge()
        if merge_code == 0:
            clear_session()   # branch merged — session no longer needed
        return merge_code
    return code


def run_check(options: DiffOptions, fail_on: set[RiskCategory]) -> int:
    """
    Non-interactive mode: diff, categorize, and exit with code 1 if any file
    matches a category in *fail_on*.  No prompts are shown.
    """
    assert_in_git_repo()

    with console.status("[bold green]Running git diff…[/bold green]"):
        raw_diff = fetch_diff(options)

    if not raw_diff.strip():
        console.print("[green]No differences found.[/green]")
        return 0

    with console.status("[bold green]Categorizing…[/bold green]"):
        diff_files = parse_diff(raw_diff)
        reviews = categorize_all(diff_files)

    if not reviews:
        console.print("[green]No files to review.[/green]")
        return 0

    failing = [r for r in reviews if r.category in fail_on]

    console.print()
    for review in sorted(reviews, key=lambda r: r.category):
        color = CATEGORY_COLORS.get(review.category, "white")
        label = CATEGORY_LABELS.get(review.category, str(review.category))
        if review.category in fail_on:
            console.print(
                f"[bold red]FAIL[/bold red]  [{color}]{label}[/{color}]"
                f"  {review.diff_file.display_path}"
            )
            for reason in review.reasons:
                console.print(f"       [dim]• {reason.description}[/dim]")
        else:
            console.print(
                f"[green] OK [/green]  [dim]{label}[/dim]"
                f"  {review.diff_file.display_path}"
            )

    console.print()
    if failing:
        fail_labels = ", ".join(
            sorted(CATEGORY_LABELS.get(c, str(c)) for c in fail_on)
        )
        console.print(
            f"[bold red]{len(failing)} file(s) matched --fail-on categories "
            f"({fail_labels}).[/bold red]"
        )
        return 1

    console.print("[bold green]No files matched --fail-on categories.[/bold green]")
    return 0


def run_summarize(options: DiffOptions) -> int:
    """
    Non-interactive mode: print a count of changed files per risk category and exit.
    """
    assert_in_git_repo()

    with console.status("[bold green]Running git diff…[/bold green]"):
        raw_diff = fetch_diff(options)

    if not raw_diff.strip():
        console.print("[green]No differences found.[/green]")
        return 0

    with console.status("[bold green]Categorizing…[/bold green]"):
        diff_files = parse_diff(raw_diff)
        reviews = categorize_all(diff_files)

    if not reviews:
        console.print("[green]No files to review.[/green]")
        return 0

    counts: dict[RiskCategory, int] = {}
    for r in reviews:
        counts[r.category] = counts.get(r.category, 0) + 1

    from rich.table import Table
    table = Table(title="Changes by Risk Category", show_header=True, header_style="bold")
    table.add_column("Risk", justify="right", no_wrap=True)
    table.add_column("Category", no_wrap=True)
    table.add_column("Files", justify="right")

    for cat in sorted(counts):
        color = CATEGORY_COLORS.get(cat, "white")
        label = CATEGORY_LABELS.get(cat, str(cat))
        table.add_row(
            f"[{color}]{cat.value}[/{color}]",
            f"[{color}]{label}[/{color}]",
            str(counts[cat]),
        )

    console.print()
    console.print(table)
    console.print(f"\n[dim]{len(reviews)} file(s) total[/dim]")
    return 0
