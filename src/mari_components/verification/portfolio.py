"""Bounded, auditable selection over repeated callable results."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from .models import AttemptFailure, ScoredAttempt, SelectionResult, VerificationScore
from .selection import numeric_score

RawT = TypeVar("RawT")
CandidateT = TypeVar("CandidateT")


def best_of_n(
    generate: Callable[[], RawT],
    parser: Callable[[RawT], CandidateT],
    scorer: Callable[[CandidateT], float | VerificationScore],
    *,
    attempts: int,
    threshold: float | None = None,
) -> SelectionResult[CandidateT]:
    """Generate, validate, and score up to ``attempts`` candidates.

    Generation, parsing, and scoring failures are retained in the result when
    another attempt succeeds. The first highest-scoring candidate wins.
    """
    if attempts < 1:
        raise ValueError("best-of-N attempts must be positive")

    scored: list[ScoredAttempt[CandidateT]] = []
    failures: list[AttemptFailure] = []
    best: ScoredAttempt[CandidateT] | None = None
    stopped_early = False

    for index in range(attempts):
        try:
            candidate = parser(generate())
            score, breakdown = numeric_score(scorer(candidate))
            attempt = ScoredAttempt(
                index=index,
                candidate=candidate,
                score=score,
                breakdown=breakdown,
            )
            scored.append(attempt)
            if best is None or attempt.score > best.score:
                best = attempt
            if threshold is not None and score >= threshold:
                stopped_early = True
                break
        except Exception as error:
            failures.append(
                AttemptFailure(
                    index=index,
                    error_type=type(error).__name__,
                    message=str(error),
                )
            )

    if best is None:
        details = "; ".join(
            f"attempt {row.index}: {row.error_type}: {row.message}"
            for row in failures
        )
        raise RuntimeError(f"best-of-N produced no valid candidate ({details})")

    return SelectionResult(
        selected=best.candidate,
        selected_index=best.index,
        attempts=tuple(scored),
        failures=tuple(failures),
        stopped_early=stopped_early,
    )
