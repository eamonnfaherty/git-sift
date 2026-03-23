# git-sift

An interactive CLI wizard for reviewing AI-generated code changes, ordered from highest to lowest risk.

`git-sift` walks you through every changed file in a diff — categorising each one by risk, showing you exactly why it was flagged, and letting you approve, raise a concern, mark a blocker, or ask Claude Code to fix it. Once everything is approved it can merge the PR for you.

---

## Why

AI-generated code changes can bury high-risk edits — a removed auth check, a bumped dependency, an altered migration — inside large diffs full of low-risk formatting changes. `git-sift` forces you to confront the riskiest files first, every time.

---

## Installation

```bash
pip install git-sift
```

Or from source:

```bash
git clone https://github.com/eamonnfaherty/git-compare-tool
cd git-compare-tool
pip install -e .
```

Requires Python 3.11+.

---

## Quick start

```bash
# In any git repository — compares current branch against main
git-sift
```

That's it. `git-sift` detects your branch, diffs it against `main` (or `master`), and opens the wizard.

---

## Usage

```bash
# Default: current branch vs main
git-sift

# Staged changes only
git-sift --staged

# Unstaged working-tree changes
git-sift --unstaged

# Specific refs
git-sift --ref-a main --ref-b feature/my-branch
git-sift --ref-a v1.0.0 --ref-b v1.1.0

# Non-interactive CI mode — exit 1 if security or dependency changes are detected
git-sift --fail-on security,dependency

# Install the Claude Code /git-sift skill
git-sift --install-skill
```

---

## Risk categories

Files are assigned the **highest-risk** (lowest number) category that matches. Both filename patterns and diff content are checked — content rules can escalate a file beyond its path-based category.

| Risk | Category | Triggers |
|------|----------|----------|
| 1 | **Security** | `*auth*`, `*secret*`, `*.pem`, `*.key` paths; removed auth checks; hardcoded secrets; `eval`/`exec`; unsafe deserialisation; unsafe `yaml.load()` |
| 2 | **Dependencies** | `requirements*.txt`, `pyproject.toml`, `package.json`, `go.mod`, `Cargo.toml`, etc.; version pin changes |
| 3 | **Infrastructure** | `Dockerfile`, CI/CD workflows, Terraform, Kubernetes, shell scripts |
| 4 | **Database Migrations** | `migrations/`, `alembic/versions/`, `*.migration.sql` |
| 5 | **Architecture Tests** | `*arch*test*`, `tests/arch/` |
| 6 | **Existing Tests** | `test_*.py`, `*.test.ts`, `__tests__/`; removed asserts; deleted test functions; added skip/xfail |
| 7 | **Existing Code** | Modified source files; added `# TODO`/`# FIXME`/`# HACK`; `raise NotImplementedError`; `pass` or `...` placeholders; commented-out code |
| 8 | **New Code** | Newly created files with no other classification |
| 9 | **Config / Environment** | `.env`, `*.yaml`, `*.cfg`, `settings*.py`, `config/` |
| 10 | **Docs & Formatting** | `*.md`, `*.rst`, `docs/`, `CHANGELOG`, `README` |

Every matched rule adds a **"Why this was flagged"** reason shown above each file's diff so you always know what to look for before reading the code.

---

## Interactive wizard

The wizard walks through files from risk 1 to 10, prompting for a decision on each:

| Key | Decision | Meaning |
|-----|----------|---------|
| `A` | **Approve** | Looks correct |
| `C` | **Concern** | Worth noting but not a hard blocker |
| `B` | **Blocker** | Must be fixed before merge |
| `S` | **Skip** | Review later |
| `Q` | **Quit** | Exit the session |
| `?` | Help | Show this table |

After **Concern** or **Blocker** you are prompted for an optional note.

A compact status bar is pinned just above the prompt at the bottom of the screen, showing the file path, category, and risk level — so it is always visible regardless of diff length.

---

## Interactive browser (second pass)

After the wizard completes its summary, an interactive file browser opens for a second pass:

| Key | Action |
|-----|--------|
| `A` | Approve this file |
| `R` | Recommend a change — launches a Claude Code session to fix it |
| `S` | Skip |
| `N` / `P` | Next / Previous file |
| `?` | Help |

### Claude-assisted fixes

Pressing **R** on any file:

1. Prompts you for a description of what needs to change
2. Builds a structured prompt including the file path, risk category, the diff, and your recommendation
3. Launches an interactive Claude Code session (`claude`) in your terminal
4. When you exit Claude, the full wizard **restarts** with a fresh diff so the fix is reviewed from scratch

Every line Claude changes receives an inline `# AI-REVIEW-FIX: <explanation>` comment. Security fixes also get `# AI-REVIEW-FIX(SECURITY): <vulnerability addressed>`. This ensures AI-introduced changes are always visible to future reviewers.

Requires the `claude` CLI to be installed and on your `PATH`.

---

## PR merge

Once all files are approved in the browser, `git-sift` offers to merge your open PR:

```
Merge this branch via PR? [Y/n]
```

Choose a merge strategy:

| Key | Strategy |
|-----|----------|
| `S` | Squash merge |
| `M` | Merge commit |
| `R` | Rebase |
| `C` | Cancel |

Requires the `gh` CLI and an open PR on the current branch. The branch is deleted after a successful merge.

---

## Non-interactive / CI mode

```bash
git-sift --fail-on CATEGORIES
```

Runs the diff, categorises all files, prints a pass/fail summary, and exits with code `1` if any file matches a listed category. No prompts.

**Category names** (comma-separated, case-insensitive):

| Name(s) | Category |
|---------|----------|
| `security` | Security |
| `dependency`, `dependencies` | Dependencies |
| `infrastructure`, `infra` | Infrastructure |
| `database`, `migrations` | Database Migrations |
| `arch`, `arch-tests` | Architecture Tests |
| `tests`, `existing-tests` | Existing Tests |
| `code`, `existing-code` | Existing Code |
| `new`, `new-code` | New Code |
| `config`, `config-env`, `env` | Config / Environment |
| `docs`, `docs-formatting`, `formatting` | Docs & Formatting |

You can also use the numeric risk level directly (`1`–`10`).

```bash
# Fail on security or dependency changes (by name)
git-sift --fail-on security,dependency

# Same using risk levels
git-sift --fail-on 1,2

# Combine with a specific diff source
git-sift --staged --fail-on security
git-sift --ref-a main --ref-b HEAD --fail-on security,infrastructure,migrations

# In a CI pipeline
git-sift --fail-on security,dependency || exit 1
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | No files matched the fail-on categories (or no diff) |
| `1` | At least one file matched a fail-on category; or a blocker found in interactive mode |
| `2` | Operational error (not in a git repo, git command failed) |

---

## Claude Code skill

Install the `/git-sift` slash command into Claude Code:

```bash
git-sift --install-skill
```

This writes `~/.claude/commands/git-sift.md` so you can type `/git-sift` inside any Claude Code session to run the wizard, interpret results, and get help addressing blockers.

---

## Detected patterns for incomplete AI code

`git-sift` specifically watches for signs that an AI left work unfinished or disabled existing functionality:

- Added `# TODO`, `# FIXME`, `# HACK`, or `# XXX` comments
- Added `raise NotImplementedError`
- Added a standalone `pass` or `...` (ellipsis placeholder)
- Added comments containing words like `disabled`, `not implemented`, `placeholder`, `temporary`, `workaround`, `for now`
- Commented-out code: lines like `# return something()`, `# validate_input(data)`

These appear as reasons in the "Why this was flagged" panel even when a higher-risk rule (like SECURITY) already governs the file's category.

---

## Requirements

- Python 3.11+
- Git
- `claude` CLI — for Claude-assisted fixes (`brew install claude` or see [claude.ai/code](https://claude.ai/code))
- `gh` CLI — for PR merge (`brew install gh`)

---

## License

[MIT](LICENSE)
