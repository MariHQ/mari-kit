"""Best-of-N selection over candidates produced by any runtime."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from typing import TypeVar

from .models import AttemptFailure, ScoredAttempt, SelectionResult, VerificationScore

CandidateT = TypeVar("CandidateT")
ScoreFunction = Callable[[CandidateT], float | VerificationScore]


def numeric_score(value: float | VerificationScore) -> tuple[float, VerificationScore | None]:
    if isinstance(value, VerificationScore):
        return value.score, value
    score = float(value)
    if not math.isfinite(score):
        raise ValueError("candidate score must be finite")
    return score, None


def select_best(
    candidates: Iterable[CandidateT],
    scorer: ScoreFunction[CandidateT],
    *,
    threshold: float | None = None,
) -> SelectionResult[CandidateT]:
    """Select the first highest-scoring candidate and retain the audit trail."""
    attempts: list[ScoredAttempt[CandidateT]] = []
    failures: list[AttemptFailure] = []
    best: ScoredAttempt[CandidateT] | None = None
    stopped_early = False
    for index, candidate in enumerate(candidates):
        try:
            score, breakdown = numeric_score(scorer(candidate))
        except Exception as error:
            failures.append(
                AttemptFailure(
                    index=index,
                    error_type=type(error).__name__,
                    message=str(error),
                )
            )
            continue
        attempt = ScoredAttempt(
            index=index, candidate=candidate, score=score, breakdown=breakdown
        )
        attempts.append(attempt)
        if best is None or attempt.score > best.score:
            best = attempt
        if threshold is not None and score >= threshold:
            stopped_early = True
            break
    if best is None:
        raise ValueError("no candidate could be scored")
    return SelectionResult(
        selected=best.candidate,
        selected_index=best.index,
        attempts=tuple(attempts),
        failures=tuple(failures),
        stopped_early=stopped_early,
    )
