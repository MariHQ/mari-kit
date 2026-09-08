"""Hindsight-inspired temporal ranking, with caller-supplied dates and scores."""

from __future__ import annotations

import calendar
import math
from datetime import UTC, datetime
from typing import Literal


def recency_decay(
    days: float,
    *,
    method: Literal["linear", "exponential", "none"] = "linear",
    window: float = 365,
    half_life: float = 90,
) -> float:
    """Map age in days to freshness; unlike upstream, reject invalid parameters."""
    if (
        not all(math.isfinite(x) for x in (days, window, half_life))
        or window <= 0
        or half_life <= 0
    ):
        raise ValueError("finite age and positive window/half_life required")
    if method == "none":
        return 0.5
    if method == "linear":
        return max(0.1, min(1.0, 1 - days / window))
    if method == "exponential":
        return 2 ** (-max(0.0, days) / half_life)
    raise ValueError("unknown decay method")


def dated_recency(
    *,
    now: datetime,
    start: datetime | None = None,
    end: datetime | None = None,
    mentioned: datetime | None = None,
    method: Literal["linear", "exponential", "none"] = "linear",
    window: float = 365,
    half_life: float = 90,
) -> float:
    """Use period end capped at neutral for month/year spans, else start/mention/end.

    Naive datetimes mean UTC. Period recognition follows Hindsight's span-length
    heuristic (one day tolerance), not a claim about the date's true granularity.
    """

    def utc(value: datetime) -> datetime:
        return (
            value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        )

    recency_decay(0, method=method, window=window, half_life=half_life)
    coarse = False
    if start is not None and end is not None:
        span = (utc(end) - utc(start)).total_seconds()
        if span < 0:
            raise ValueError("end precedes start")
        periods = (
            calendar.monthrange(start.year, start.month)[1] * 86400,
            (366 if calendar.isleap(start.year) else 365) * 86400,
        )
        coarse = any(period - 86400 <= span <= period for period in periods)
    instant = end if coarse else start or mentioned or end
    if instant is None:
        return 0.5
    score = recency_decay(
        (utc(now) - utc(instant)).total_seconds() / 86400,
        method=method,
        window=window,
        half_life=half_life,
    )
    return min(0.5, score) if coarse else score


def temporal_proof_score(
    relevance: float,
    *,
    recency: float = 0.5,
    proximity: float = 0.5,
    proof_count: int | None = None,
    recency_alpha: float = 0.2,
    temporal_alpha: float = 0.2,
    proof_alpha: float = 0.1,
) -> float:
    """Multiply normalized relevance by neutral-centered freshness/time/proof boosts."""
    if any(
        not math.isfinite(x) or not 0 <= x <= 1 for x in (relevance, recency, proximity)
    ):
        raise ValueError("signals must be finite in [0, 1]")
    if any(
        not math.isfinite(x) or not 0 <= x <= 2
        for x in (recency_alpha, temporal_alpha, proof_alpha)
    ):
        raise ValueError("alphas must be in [0, 2]")
    if proof_count is not None and (
        not isinstance(proof_count, int) or proof_count < 0
    ):
        raise ValueError("proof_count must be a nonnegative integer")
    proof = min(1.0, 0.5 + math.log(proof_count) / 10) if proof_count else 0.5
    return (
        relevance
        * (1 + recency_alpha * (recency - 0.5))
        * (1 + temporal_alpha * (proximity - 0.5))
        * (1 + proof_alpha * (proof - 0.5))
    )
