"""Budgeted, model-neutral consolidation and promotion planning."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class PromotionSignal:
    artifact_id: str
    recurrence: float
    recency: float
    usefulness: float
    evidence_diversity: float
    estimated_calls: int = 1
    estimated_tokens: int = 0

    def __post_init__(self) -> None:
        if not self.artifact_id.strip():
            raise ValueError("artifact ID is required")
        values = (
            self.recurrence,
            self.recency,
            self.usefulness,
            self.evidence_diversity,
        )
        if any(not math.isfinite(value) or not 0 <= value <= 1 for value in values):
            raise ValueError("promotion signals must be finite values in [0, 1]")
        if self.estimated_calls < 0 or self.estimated_tokens < 0:
            raise ValueError("estimated costs must not be negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class ConsolidationBudget:
    max_model_calls: int
    max_tokens: int

    def __post_init__(self) -> None:
        if self.max_model_calls < 0 or self.max_tokens < 0:
            raise ValueError("consolidation budgets must not be negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class ConsolidationPlan:
    selected_ids: tuple[str, ...]
    deferred_ids: tuple[str, ...]
    scores: tuple[tuple[str, float], ...]
    model_calls: int
    tokens: int


def plan_consolidation(
    signals: Iterable[PromotionSignal],
    *,
    budget: ConsolidationBudget,
    weights: tuple[float, float, float, float] = (0.3, 0.15, 0.35, 0.2),
    minimum_score: float = 0.0,
) -> ConsolidationPlan:
    """Select highest-value promotions under call and token budgets."""

    values = tuple(signals)
    ids = [value.artifact_id for value in values]
    if len(ids) != len(set(ids)):
        raise ValueError("artifact IDs must be unique")
    if (
        len(weights) != 4
        or any(not math.isfinite(value) or value < 0 for value in weights)
        or sum(weights) == 0
    ):
        raise ValueError(
            "weights must contain four non-negative finite values with a positive sum"
        )
    if not math.isfinite(minimum_score):
        raise ValueError("minimum_score must be finite")
    total_weight = sum(weights)
    normalized = tuple(value / total_weight for value in weights)
    scored = [
        (
            sum(
                component * weight
                for component, weight in zip(
                    (
                        row.recurrence,
                        row.recency,
                        row.usefulness,
                        row.evidence_diversity,
                    ),
                    normalized,
                    strict=True,
                )
            ),
            row,
        )
        for row in values
    ]
    ranked = sorted(scored, key=lambda pair: (-pair[0], pair[1].artifact_id))
    selected: list[str] = []
    deferred: list[str] = []
    calls = tokens = 0
    for score, row in ranked:
        fits = (
            calls + row.estimated_calls <= budget.max_model_calls
            and tokens + row.estimated_tokens <= budget.max_tokens
        )
        if score >= minimum_score and fits:
            selected.append(row.artifact_id)
            calls += row.estimated_calls
            tokens += row.estimated_tokens
        else:
            deferred.append(row.artifact_id)
    return ConsolidationPlan(
        selected_ids=tuple(selected),
        deferred_ids=tuple(deferred),
        scores=tuple((row.artifact_id, score) for score, row in ranked),
        model_calls=calls,
        tokens=tokens,
    )
