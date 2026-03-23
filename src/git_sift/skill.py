"""Generates and installs the Claude Code /git-sift skill."""
from __future__ import annotations

from pathlib import Path

SKILL_FILENAME = "git-sift.md"

SKILL_CONTENT = """\
# /git-sift

Run `git-sift` to walk through the current repository's diff as a risk-ordered
code-review wizard, then help the user address any issues found.

## Steps

1. Run the review wizard:
   ```bash
   git-sift
   ```
   If the user wants to review staged changes, use `git-sift --staged`.
   If they want to compare specific refs, use `git-sift --ref-a <base> --ref-b <head>`.

2. Walk through the interactive prompts with the user:
   - **A** Approve, **C** Concern, **B** Blocker, **S** Skip, **Q** Quit
   - Add notes to Concerns and Blockers explaining the issue.

3. After the wizard summary, interpret the results:
   - List any **Blockers** and explain why each one is a problem.
   - List any **Concerns** and suggest whether they need addressing before merge.
   - If everything is approved, confirm it is safe to proceed to merge.

4. If the user wants to fix a blocker, either:
   - Guide them through the fix manually, or
   - Use the interactive browser (it opens automatically after the wizard) and press **R**
     on the relevant file to launch a Claude-assisted fix session.

---

## Risk categories (highest → lowest)

| Risk | Category | What to watch for |
|------|----------|--------------------|
| 1 | Security | Auth check removals, hardcoded secrets, unsafe deserialisation, `eval`/`exec` |
| 2 | Dependencies | Version bumps in requirements, package.json, go.mod, Cargo.toml |
| 3 | Infrastructure | Dockerfile, CI/CD workflows, Terraform, Kubernetes |
| 4 | Database Migrations | Schema changes, alembic versions, raw SQL |
| 5 | Architecture Tests | Structural constraint tests |
| 6 | Existing Tests | Removed asserts, deleted test functions, added skip/xfail |
| 7 | Existing Code | Modified source — also flags TODOs, commented-out code, placeholders |
| 8 | New Code | Newly created files |
| 9 | Config / Env | .env, YAML configs, settings modules |
| 10 | Docs & Formatting | Markdown, RST, documentation |

## Non-interactive CI check

To check for risky changes without prompting (useful in CI or pre-push hooks):

```bash
# Exit 1 if any security or dependency changes are detected
git-sift --fail-on security,dependency

# Using numeric risk levels
git-sift --fail-on 1,2

# Combine with a diff source
git-sift --staged --fail-on security
```

## Tips for reviewing AI-generated code

- **Security first** — AI models sometimes silently remove auth guards or inline secrets.
- **Scrutinise dependency bumps** — AI may update to latest without checking compatibility.
- **Check migrations carefully** — Schema changes are hard to reverse.
- **Look for commented-out code** — AI occasionally disables existing logic instead of fixing it.
- **Watch for TODOs and placeholders** — Signs the AI deferred something it couldn't implement.
- **Trace config changes** — Small .env or YAML edits can have large production impact.
- **Use Blocker liberally** — Cheaper to block a PR than revert a deploy.
"""


def skill_install_path() -> Path:
    """Return the path where the skill should be installed."""
    return Path.home() / ".claude" / "commands" / SKILL_FILENAME


def install_skill() -> tuple[bool, Path]:
    """
    Write the skill file to ~/.claude/commands/git-sift.md.

    Returns (already_existed, destination_path).
    """
    dest = skill_install_path()
    already_existed = dest.exists()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(SKILL_CONTENT, encoding="utf-8")
    return already_existed, dest
