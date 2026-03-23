"""PR merge utilities."""
from __future__ import annotations

import json
import shutil
import subprocess

from rich.prompt import Prompt

from git_sift.renderer import console


def check_working_tree_clean() -> bool:
    """Return True if there are no uncommitted changes in the working tree."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == ""


def check_pr_exists() -> dict | None:
    """
    Return PR metadata dict or None.

    Returns None if `gh` is not installed, no PR is open, or the command fails.
    """
    if shutil.which("gh") is None:
        return None
    result = subprocess.run(
        ["gh", "pr", "view", "--json", "number,state,headRefName,url"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if data.get("state", "").upper() != "OPEN":
        return None
    return data


def prompt_and_merge() -> int:
    """
    Interactively prompt the user for a merge strategy and merge the open PR.

    Returns 0 on success, 1 on cancel or failure.
    """
    if not check_working_tree_clean():
        console.print(
            "[bold red]Working tree is not clean.[/bold red]\n"
            "Please commit or stash your changes before merging."
        )
        return 1

    pr = check_pr_exists()
    if pr is None:
        console.print(
            "[bold red]No open PR found.[/bold red]\n"
            "Push your branch and create a PR first, then re-run git-sift."
        )
        return 1

    console.print(
        f"\n[bold]Open PR:[/bold] #{pr['number']}  "
        f"[cyan]{pr.get('headRefName', '')}[/cyan]\n"
        f"  {pr.get('url', '')}"
    )

    console.print(
        "\n[bold]Merge strategy:[/bold]\n"
        "  [cyan]S[/cyan]  Squash merge\n"
        "  [cyan]M[/cyan]  Merge commit\n"
        "  [cyan]R[/cyan]  Rebase\n"
        "  [cyan]C[/cyan]  Cancel\n"
    )

    choice = Prompt.ask(
        "[S]quash  [M]erge commit  [R]ebase  [C]ancel",
        default="S",
        console=console,
    ).strip().lower()

    if choice == "c":
        console.print("[dim]Merge cancelled.[/dim]")
        return 1

    flag_map = {"s": "--squash", "m": "--merge", "r": "--rebase"}
    flag = flag_map.get(choice)
    if flag is None:
        console.print("[red]Invalid choice — merge cancelled.[/red]")
        return 1

    console.print(f"[bold green]Merging PR #{pr['number']}…[/bold green]")
    result = subprocess.run(
        ["gh", "pr", "merge", flag, "--delete-branch"],
        text=True,
    )
    if result.returncode == 0:
        console.print("[bold green]PR merged and branch deleted.[/bold green]")
        return 0
    else:
        console.print("[bold red]Merge failed. Check `gh pr merge` output above.[/bold red]")
        return 1
