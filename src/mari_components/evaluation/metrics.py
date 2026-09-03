"""Deterministic metrics for retrieval and labeled decisions."""

from __future__ import annotations

import math
from collections.abc import Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class RetrievalMetrics:
    precision: float
    recall: float
    reciprocal_rank: float
    ndcg: float


@dataclass(frozen=True, slots=True, kw_only=True)
class ClassificationMetrics:
    accuracy: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    support: int


@dataclass(frozen=True, slots=True, kw_only=True)
class SetMetrics:
    precision: float
    recall: float
    f1: float
    true_positive: int
    false_positive: int
    false_negative: int


def set_metrics(
    expected: Iterable[Hashable], predicted: Iterable[Hashable]
) -> SetMetrics:
    """Score an evidence/entity/relation set with exact identifiers."""

    expected_values = set(expected)
    predicted_values = set(predicted)
    true_positive = len(expected_values & predicted_values)
    false_positive = len(predicted_values - expected_values)
    false_negative = len(expected_values - predicted_values)
    precision = true_positive / len(predicted_values) if predicted_values else 0.0
    recall = true_positive / len(expected_values) if expected_values else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return SetMetrics(
        precision=precision,
        recall=recall,
        f1=f1,
        true_positive=true_positive,
        false_positive=false_positive,
        false_negative=false_negative,
    )


def boundary_metrics(
    expected_boundaries: Iterable[int],
    predicted_boundaries: Iterable[int],
    *,
    tolerance: int = 0,
) -> SetMetrics:
    """Match ordered topic boundaries once within an optional offset tolerance."""

    if tolerance < 0:
        raise ValueError("tolerance must not be negative")
    expected = sorted(set(expected_boundaries))
    predicted = sorted(set(predicted_boundaries))
    if any(value < 0 for value in (*expected, *predicted)):
        raise ValueError("boundaries must not be negative")
    unmatched = set(expected)
    hits = 0
    for value in predicted:
        options = sorted(
            (
                candidate
                for candidate in unmatched
                if abs(candidate - value) <= tolerance
            ),
            key=lambda candidate: (abs(candidate - value), candidate),
        )
        if options:
            unmatched.remove(options[0])
            hits += 1
    precision = hits / len(predicted) if predicted else 0.0
    recall = hits / len(expected) if expected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return SetMetrics(
        precision=precision,
        recall=recall,
        f1=f1,
        true_positive=hits,
        false_positive=len(predicted) - hits,
        false_negative=len(expected) - hits,
    )


def reciprocal_rank(
    ranked_ids: Sequence[Hashable], relevant_ids: Iterable[Hashable]
) -> float:
    relevant = set(relevant_ids)
    return next(
        (1.0 / rank for rank, item in enumerate(ranked_ids, 1) if item in relevant), 0.0
    )


def ndcg_at_k(
    ranked_ids: Sequence[Hashable],
    relevance: Mapping[Hashable, float],
    *,
    k: int,
) -> float:
    """Normalized discounted cumulative gain with exponential gain."""

    if k < 1:
        raise ValueError("k must be positive")

    def dcg(grades: Iterable[float]) -> float:
        return sum(
            (2.0**grade - 1.0) / math.log2(rank + 1)
            for rank, grade in enumerate(grades, 1)
        )

    observed = dcg(float(relevance.get(item, 0.0)) for item in ranked_ids[:k])
    ideal = dcg(
        sorted((float(value) for value in relevance.values()), reverse=True)[:k]
    )
    return observed / ideal if ideal else 0.0


def evaluate_retrieval(
    ranked_ids: Sequence[Hashable],
    relevance: Mapping[Hashable, float],
    *,
    k: int = 10,
) -> RetrievalMetrics:
    """Score one query; callers macro-average these values across query IDs."""

    if k < 1:
        raise ValueError("k must be positive")
    observed = tuple(ranked_ids[:k])
    relevant = {item for item, grade in relevance.items() if grade > 0}
    hits = sum(item in relevant for item in observed)
    return RetrievalMetrics(
        precision=hits / k,
        recall=hits / len(relevant) if relevant else 0.0,
        reciprocal_rank=reciprocal_rank(observed, relevant),
        ndcg=ndcg_at_k(observed, relevance, k=k),
    )


def classification_metrics(
    expected: Sequence[Hashable],
    predicted: Sequence[Hashable],
) -> ClassificationMetrics:
    """Compute accuracy and unweighted per-class precision, recall, and F1."""

    if len(expected) != len(predicted):
        raise ValueError("expected and predicted lengths differ")
    if not expected:
        return ClassificationMetrics(
            accuracy=0.0, macro_precision=0.0, macro_recall=0.0, macro_f1=0.0, support=0
        )
    labels = set(expected) | set(predicted)
    precision_values: list[float] = []
    recall_values: list[float] = []
    f1_values: list[float] = []
    for label in labels:
        true_positive = sum(
            e == label and p == label for e, p in zip(expected, predicted, strict=True)
        )
        false_positive = sum(
            e != label and p == label for e, p in zip(expected, predicted, strict=True)
        )
        false_negative = sum(
            e == label and p != label for e, p in zip(expected, predicted, strict=True)
        )
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )
        f1 = (
            2 * precision * recall / (precision + recall) if precision + recall else 0.0
        )
        precision_values.append(precision)
        recall_values.append(recall)
        f1_values.append(f1)
    count = len(expected)
    return ClassificationMetrics(
        accuracy=sum(e == p for e, p in zip(expected, predicted, strict=True)) / count,
        macro_precision=sum(precision_values) / len(labels),
        macro_recall=sum(recall_values) / len(labels),
        macro_f1=sum(f1_values) / len(labels),
        support=count,
    )
