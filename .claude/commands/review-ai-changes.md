# /review-ai-changes

Walk through AI-generated code changes interactively, ordered from highest to lowest risk.

## What it does

`git-sift` is a CLI wizard that:
1. Runs `git diff` (staged, unstaged, or between refs)
2. Categorizes every changed file by risk using path patterns and content analysis
3. Steps you through each file from highest to lowest risk
4. Collects your decision (Approve / Concern / Blocker / Skip) for each file
5. Prints a summary and exits with code `1` if any blockers were found

This is especially useful when reviewing AI-generated PRs where subtle changes (removed auth checks, bumped dependency versions, altered migrations) can be buried in large diffs.

---

## Install

```bash
cd /path/to/git-compare-tool
pip install -e .
```

Or with a virtual environment:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

---

## Usage

```bash
# Compare current branch against main (default — no flags needed)
git-sift

# Review staged changes only
git-sift --staged

# Review unstaged working-tree changes
git-sift --unstaged

# Compare two specific refs
git-sift --ref-a main --ref-b feature/my-branch
git-sift --ref-a v1.0.0 --ref-b v1.1.0

# In a CI pipeline (non-zero exit on blockers)
git-sift --ref-a main --ref-b HEAD || exit 1
```

---

## Risk categories (highest → lowest)

| # | Category | What to watch for |
|---|---|---|
| 1 | **Security** | Auth check removals, hardcoded secrets, unsafe deserialization, dynamic code execution |
| 2 | **Dependencies** | Version bumps/pins in requirements, package.json, go.mod, Cargo.toml |
| 3 | **Infrastructure** | Dockerfile changes, CI/CD workflows, Terraform, Kubernetes manifests |
| 4 | **Database Migrations** | Schema changes, alembic versions, raw SQL migrations |
| 5 | **Architecture Tests** | Structural/dependency rule tests that enforce design constraints |
| 6 | **Existing Tests** | Removed asserts, deleted test functions, added skip/xfail markers |
| 7 | **Existing Code** | Modified source files with no other classification |
| 8 | **New Code** | Newly created files |
| 9 | **Config / Environment** | .env files, YAML configs, settings modules |
| 10 | **Docs & Formatting** | Markdown, RST, documentation-only changes |

**Highest risk wins:** a file matching both SECURITY patterns and TEST patterns is classified as SECURITY.

---

## Review decisions

| Key | Decision | Meaning |
|-----|---|---|
| `A` | **Approve** | Looks correct — no issues |
| `C` | **Concern** | Something worth noting but not a hard blocker |
| `B` | **Blocker** | Must be fixed before this can be merged |
| `S` | **Skip** | Not reviewing now (counts as unreviewed in summary) |
| `?` | Help | Show the decision menu |

After choosing **Concern** or **Blocker**, you'll be prompted for an optional note explaining the issue.

---

## Exit codes

| Code | Meaning |
|------|---|
| `0` | Review complete, no blockers |
| `1` | At least one BLOCKER found |
| `2` | Operational error (git not found, not in a repo, git command failed) |

---

## Tips for reviewing AI-generated code

1. **Start with Security** — AI models sometimes remove auth guards or inline secrets. Check these first.
2. **Scrutinize dependency bumps** — AI may update packages to latest without verifying compatibility.
3. **Check migrations carefully** — Schema changes are hard to reverse. Look for data-destructive operations (`DROP`, `DELETE`, column type changes).
4. **Look at removed test code** — AI occasionally deletes tests rather than fixing them.
5. **Trace config changes** — Small .env or YAML changes can have large production impact.
6. **Use Blocker liberally** — It's cheaper to block a PR than to revert a deploy.
7. **Add notes to concerns** — Future you will thank present you.

---

## Running from this Claude Code session

```bash
# Install first (once per machine)
pip install -e /path/to/git-compare-tool

# Then in any git repository
git-sift
```
