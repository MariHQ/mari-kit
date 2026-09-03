"""Paired uncertainty, slice summaries, reliability, and repeated-trial metrics."""

from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True, slots=True, kw_only=True)
class PairedMetric:
    case_id: str
    baseline: float
    candidate: float
    slices: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not all(
            math.isfinite(value) for value in (self.baseline, self.candidate)
        ):
            raise ValueError("paired metric requires an ID and finite scores")
        object.__setattr__(self, "slices", MappingProxyType(dict(self.slices)))


@dataclass(frozen=True, slots=True, kw_only=True)
class PairedMetricComparison:
    sample_size: int
    baseline_mean: float
    candidate_mean: float
    mean_delta: float
    confidence_interval: tuple[float, float]
    confidence: float
    wins: int
    ties: int
    losses: int


@dataclass(frozen=True, slots=True, kw_only=True)
class SliceComparison:
    slice_key: str
    slice_value: str
    comparison: PairedMetricComparison


@dataclass(frozen=True, slots=True, kw_only=True)
class ReviewLabel:
    item_id: str
    reviewer_id: str
    label: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ReviewReliability:
    item_count: int
    reviewer_count: int
    pair_count: int
    observed_agreement: float
    expected_agreement: float
    kappa: float
    duplicate_pairs: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class RepeatedTrialResult:
    task_id: str
    attempts: tuple[bool, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class PassKSummary:
    tasks: int
    attempts_per_task: tuple[int, ...]
    pass_at_least_k: Mapping[int, float]
    pass_all_k: Mapping[int, float]


def compare_paired_metrics(
    observations: Iterable[PairedMetric],
    *,
    confidence: float = 0.95,
    bootstrap_samples: int = 10_000,
    seed: int = 0,
) -> PairedMetricComparison:
    """Bootstrap a paired mean delta while retaining wins, ties, and losses."""

    values = tuple(observations)
    if not values or len({item.case_id for item in values}) != len(values):
        raise ValueError("paired observations require unique non-empty case IDs")
    if not 0 < confidence < 1 or bootstrap_samples < 1:
        raise ValueError("confidence and bootstrap_samples are invalid")
    deltas = [item.candidate - item.baseline for item in values]
    generator = random.Random(seed)
    bootstrapped = sorted(
        sum(deltas[generator.randrange(len(deltas))] for _ in deltas) / len(deltas)
        for _ in range(bootstrap_samples)
    )
    tail = (1 - confidence) / 2
    low = bootstrapped[min(int(tail * bootstrap_samples), bootstrap_samples - 1)]
    high = bootstrapped[min(int((1 - tail) * bootstrap_samples), bootstrap_samples - 1)]
    return PairedMetricComparison(
        sample_size=len(values),
        baseline_mean=sum(item.baseline for item in values) / len(values),
        candidate_mean=sum(item.candidate for item in values) / len(values),
        mean_delta=sum(deltas) / len(deltas),
        confidence_interval=(low, high),
        confidence=confidence,
        wins=sum(delta > 0 for delta in deltas),
        ties=sum(delta == 0 for delta in deltas),
        losses=sum(delta < 0 for delta in deltas),
    )


def evaluate_slices(
    observations: Iterable[PairedMetric],
    *,
    keys: Iterable[str],
    confidence: float = 0.95,
    bootstrap_samples: int = 2_000,
    seed: int = 0,
) -> tuple[SliceComparison, ...]:
    """Compare the same paired metric within caller-defined categorical slices."""

    values = tuple(observations)
    groups: dict[tuple[str, str], list[PairedMetric]] = {}
    for key in keys:
        for item in values:
            if key in item.slices:
                groups.setdefault((key, item.slices[key]), []).append(item)
    return tuple(
        SliceComparison(
            slice_key=key,
            slice_value=value,
            comparison=compare_paired_metrics(
                rows,
                confidence=confidence,
                bootstrap_samples=bootstrap_samples,
                seed=seed,
            ),
        )
        for (key, value), rows in sorted(groups.items())
    )


def summarize_review_reliability(
    reviews: Iterable[ReviewLabel],
) -> ReviewReliability:
    """Compute nominal pairwise agreement and chance-corrected kappa."""

    values = tuple(reviews)
    by_pair: dict[tuple[str, str], ReviewLabel] = {}
    duplicates: set[tuple[str, str]] = set()
    for review in values:
        if (
            not review.item_id.strip()
            or not review.reviewer_id.strip()
            or not review.label
        ):
            raise ValueError("review identity and label are required")
        key = (review.item_id, review.reviewer_id)
        if key in by_pair:
            duplicates.add(key)
            continue
        by_pair[key] = review
    by_item: dict[str, list[str]] = {}
    for review in by_pair.values():
        by_item.setdefault(review.item_id, []).append(review.label)
    agreements = total_pairs = 0
    for labels in by_item.values():
        for left in range(len(labels)):
            for right in range(left + 1, len(labels)):
                total_pairs += 1
                agreements += int(labels[left] == labels[right])
    frequencies = Counter(review.label for review in by_pair.values())
    count = sum(frequencies.values())
    expected = (
        sum((value / count) ** 2 for value in frequencies.values()) if count else 0.0
    )
    observed = agreements / total_pairs if total_pairs else 0.0
    kappa = (observed - expected) / (1 - expected) if expected < 1 else 1.0
    return ReviewReliability(
        item_count=len(by_item),
        reviewer_count=len({review.reviewer_id for review in by_pair.values()}),
        pair_count=total_pairs,
        observed_agreement=observed,
        expected_agreement=expected,
        kappa=kappa,
        duplicate_pairs=tuple(sorted(duplicates)),
    )


def summarize_repeated_trials(
    results: Iterable[RepeatedTrialResult],
) -> PassKSummary:
    """Estimate pass@k (any success) and pass^k (all successes) without ordering."""

    values = tuple(results)
    if not values or len({item.task_id for item in values}) != len(values):
        raise ValueError("repeated trials require unique task IDs")
    maximum = max(len(item.attempts) for item in values)
    if maximum == 0:
        raise ValueError("each task requires at least one attempt")
    at_least: dict[int, float] = {}
    all_k: dict[int, float] = {}
    for k in range(1, maximum + 1):
        eligible = [item for item in values if len(item.attempts) >= k]
        at_least[k] = sum(
            1
            - (
                math.comb(len(item.attempts) - sum(item.attempts), k)
                / math.comb(len(item.attempts), k)
                if len(item.attempts) - sum(item.attempts) >= k
                else 0.0
            )
            for item in eligible
        ) / len(eligible)
        all_k[k] = sum(
            math.comb(sum(item.attempts), k) / math.comb(len(item.attempts), k)
            if sum(item.attempts) >= k
            else 0.0
            for item in eligible
        ) / len(eligible)
    return PassKSummary(
        tasks=len(values),
        attempts_per_task=tuple(len(item.attempts) for item in values),
        pass_at_least_k=MappingProxyType(at_least),
        pass_all_k=MappingProxyType(all_k),
    )
