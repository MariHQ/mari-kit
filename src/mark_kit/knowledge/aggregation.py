"""Policy-neutral scalar uncertainty and weighted aggregation utilities."""

from __future__ import annotations

import math
from collections.abc import Hashable, Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class ScalarEstimate:
    value: float
    lower: float
    upper: float
    level: float | None = None

    def __post_init__(self) -> None:
        if not all(
            math.isfinite(value) for value in (self.value, self.lower, self.upper)
        ):
            raise ValueError("estimate values must be finite")
        if not self.lower <= self.value <= self.upper:
            raise ValueError("estimate bounds must contain the point value")
        if self.level is not None and (
            not math.isfinite(self.level) or not 0 < self.level < 1
        ):
            raise ValueError("estimate level must be between zero and one")


@dataclass(frozen=True, slots=True, kw_only=True)
class WeightedObservation:
    observation_id: Hashable
    value: float
    weight: float
    group: Hashable | None = None

    def __post_init__(self) -> None:
        if (
            not math.isfinite(self.value)
            or not math.isfinite(self.weight)
            or self.weight < 0
        ):
            raise ValueError("observation value and non-negative weight must be finite")


@dataclass(frozen=True, slots=True, kw_only=True)
class WeightedContribution:
    observation_id: Hashable
    value: float
    weight: float
    normalized_weight: float
    contribution: float
    group: Hashable | None


@dataclass(frozen=True, slots=True, kw_only=True)
class WeightedMean:
    value: float
    total_weight: float
    contributions: tuple[WeightedContribution, ...]
    excluded_zero_weight_ids: tuple[Hashable, ...]


def weighted_mean(observations: Iterable[WeightedObservation]) -> WeightedMean:
    """Calculate a weighted mean and retain every numerical contribution."""

    values = tuple(observations)
    positive = tuple(value for value in values if value.weight > 0)
    total = sum(value.weight for value in positive)
    if total <= 0:
        raise ValueError("at least one positive observation weight is required")
    contributions = tuple(
        WeightedContribution(
            observation_id=value.observation_id,
            value=value.value,
            weight=value.weight,
            normalized_weight=value.weight / total,
            contribution=value.value * value.weight / total,
            group=value.group,
        )
        for value in positive
    )
    return WeightedMean(
        value=sum(value.contribution for value in contributions),
        total_weight=total,
        contributions=contributions,
        excluded_zero_weight_ids=tuple(
            value.observation_id for value in values if value.weight == 0
        ),
    )


def wilson_proportion(
    successes: int, total: int, *, z: float = 1.959963984540054
) -> ScalarEstimate:
    """Return a Wilson score interval without interpreting the outcome label."""

    if successes < 0 or total < 1 or successes > total:
        raise ValueError("successes must be between zero and the positive total")
    if not math.isfinite(z) or z <= 0:
        raise ValueError("z must be positive and finite")
    proportion = successes / total
    denominator = 1 + z**2 / total
    center = (proportion + z**2 / (2 * total)) / denominator
    radius = (
        z
        * math.sqrt(proportion * (1 - proportion) / total + z**2 / (4 * total**2))
        / denominator
    )
    return ScalarEstimate(
        value=proportion,
        lower=max(0.0, center - radius),
        upper=min(1.0, center + radius),
        level=math.erf(z / math.sqrt(2)),
    )
