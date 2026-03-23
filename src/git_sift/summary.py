"""Build and evaluate the end-of-session summary."""
from __future__ import annotations

from git_sift.models import FileReview, ReviewDecision, SessionSummary, RiskCategory


def build_summary(reviews: list[FileReview]) -> SessionSummary:
    from collections import defaultdict
    per_category: dict[RiskCategory, dict[str, int]] = defaultdict(
        lambda: {"approve": 0, "concern": 0, "blocker": 0, "skip": 0}
    )

    blockers: list[FileReview] = []
    concerns: list[FileReview] = []

    for r in reviews:
        if r.decision == ReviewDecision.BLOCKER:
            blockers.append(r)
            per_category[r.category]["blocker"] += 1
        elif r.decision == ReviewDecision.CONCERN:
            concerns.append(r)
            per_category[r.category]["concern"] += 1
        elif r.decision == ReviewDecision.APPROVE:
            per_category[r.category]["approve"] += 1
        else:
            per_category[r.category]["skip"] += 1

    return SessionSummary(
        per_category=dict(per_category),
        blockers=blockers,
        concerns=concerns,
    )


def exit_code(summary: SessionSummary) -> int:
    return 1 if summary.has_blockers else 0
