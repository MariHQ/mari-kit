"""Fellegi--Sunter entity-resolution scoring with explicit review bands."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True, kw_only=True)
class FieldAgreement:
    """One comparison outcome and its match/non-match probabilities."""

    field: str
    agrees: bool
    match_probability: float
    nonmatch_probability: float

    def __post_init__(self) -> None:
        if not self.field.strip():
            raise ValueError("field is required")
        values = (self.match_probability, self.nonmatch_probability)
        if any(not math.isfinite(value) or not 0 < value < 1 for value in values):
            raise ValueError("field probabilities must be finite values in (0, 1)")


class ResolutionDecision(StrEnum):
    LINK = "link"
    REVIEW = "review"
    DISTINCT = "distinct"


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolutionResult:
    decision: ResolutionDecision
    score: float
    link_threshold: float
    review_threshold: float
    contributions: tuple[tuple[str, float], ...]


def fellegi_sunter_score(
    agreements: Iterable[FieldAgreement],
) -> tuple[float, tuple[tuple[str, float], ...]]:
    """Return the sum of field log-likelihood ratios and its trace."""

    values = tuple(agreements)
    if not values:
        raise ValueError("at least one field agreement is required")
    fields = [value.field for value in values]
    if len(fields) != len(set(fields)):
        raise ValueError("field agreements must be unique")
    trace = tuple(
        (
            value.field,
            math.log(
                value.match_probability / value.nonmatch_probability
                if value.agrees
                else (1 - value.match_probability) / (1 - value.nonmatch_probability)
            ),
        )
        for value in values
    )
    return sum(contribution for _field, contribution in trace), trace


def resolve_entity(
    agreements: Iterable[FieldAgreement],
    *,
    link_threshold: float,
    review_threshold: float,
) -> ResolutionResult:
    """Classify a comparison while preserving every field contribution."""

    if not all(math.isfinite(value) for value in (link_threshold, review_threshold)):
        raise ValueError("thresholds must be finite")
    if review_threshold >= link_threshold:
        raise ValueError("review_threshold must be below link_threshold")
    score, trace = fellegi_sunter_score(agreements)
    decision = (
        ResolutionDecision.LINK
        if score >= link_threshold
        else ResolutionDecision.REVIEW
        if score >= review_threshold
        else ResolutionDecision.DISTINCT
    )
    return ResolutionResult(
        decision=decision,
        score=score,
        link_threshold=link_threshold,
        review_threshold=review_threshold,
        contributions=trace,
    )
