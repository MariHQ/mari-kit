"""Typed handoffs from ranked IDs to artifact-neutral context material."""

from __future__ import annotations

import math
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Generic, TypeVar

from mari_components.knowledge.artifacts import ArtifactRef

HitT = TypeVar("HitT")


@dataclass(frozen=True, slots=True, kw_only=True)
class RetrievalUnit:
    ref: ArtifactRef
    text: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("retrieval unit text is required")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True, kw_only=True)
class HydratedHit(Generic[HitT]):
    hit: HitT
    item_id: str
    score: float
    rank: int
    unit: RetrievalUnit | None
    error: str = ""


def hydrate_hits(
    hits: Iterable[HitT],
    *,
    identity: Callable[[HitT], str],
    score: Callable[[HitT], float],
    resolve: Callable[[str], RetrievalUnit | None],
) -> tuple[HydratedHit[HitT], ...]:
    """Resolve ranked IDs without losing order, score, misses, or errors."""

    result: list[HydratedHit[HitT]] = []
    for rank, hit in enumerate(hits, 1):
        item_id = identity(hit)
        value = float(score(hit))
        if not item_id or not math.isfinite(value):
            raise ValueError("hit IDs and scores must be non-empty and finite")
        try:
            unit = resolve(item_id)
            error = "" if unit is not None else "not_found"
        except Exception as caught:  # noqa: BLE001 - resolution failures are data
            unit = None
            error = f"{type(caught).__name__}: {caught}"
        result.append(
            HydratedHit(
                hit=hit,
                item_id=item_id,
                score=value,
                rank=rank,
                unit=unit,
                error=error,
            )
        )
    return tuple(result)


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextItem:
    unit: RetrievalUnit
    score: float
    costs: Mapping[str, float]
    eligible: bool = True
    exclusion_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        values = {name: float(value) for name, value in self.costs.items()}
        if not math.isfinite(self.score):
            raise ValueError("context score must be finite")
        if any(
            not name or not math.isfinite(value) or value < 0
            for name, value in values.items()
        ):
            raise ValueError("context costs must be named, finite, and non-negative")
        object.__setattr__(self, "costs", MappingProxyType(values))
        object.__setattr__(
            self, "exclusion_reasons", tuple(dict.fromkeys(self.exclusion_reasons))
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextSelectionTrace:
    ref: ArtifactRef
    included: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextSelection:
    items: tuple[ContextItem, ...]
    totals: Mapping[str, float]
    trace: tuple[ContextSelectionTrace, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "totals", MappingProxyType(dict(self.totals)))

    @property
    def visible_refs(self) -> tuple[ArtifactRef, ...]:
        return tuple(item.unit.ref for item in self.items)

    def render(self, *, separator: str = "\n\n") -> str:
        return separator.join(item.unit.text for item in self.items)


@dataclass(frozen=True, slots=True, kw_only=True)
class DiverseSelectionTrace:
    ref: ArtifactRef
    included: bool
    groups: tuple[Hashable, ...]
    marginal_gain: float | None
    reasons: tuple[str, ...]
    selection_order: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class DiverseCandidateEvaluation:
    ref: ArtifactRef
    groups: tuple[Hashable, ...]
    marginal_gain: float | None
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class DiverseSelectionRound:
    iteration: int
    unmet_groups: tuple[Hashable, ...]
    candidates: tuple[DiverseCandidateEvaluation, ...]
    selected_ref: ArtifactRef | None
    stop_reason: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class DiverseContextSelection:
    items: tuple[ContextItem, ...]
    totals: Mapping[str, float]
    group_counts: Mapping[Hashable, int]
    unsatisfied_groups: tuple[Hashable, ...]
    trace: tuple[DiverseSelectionTrace, ...]
    rounds: tuple[DiverseSelectionRound, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "totals", MappingProxyType(dict(self.totals)))
        object.__setattr__(
            self, "group_counts", MappingProxyType(dict(self.group_counts))
        )

    @property
    def visible_refs(self) -> tuple[ArtifactRef, ...]:
        return tuple(item.unit.ref for item in self.items)

    def render(self, *, separator: str = "\n\n") -> str:
        return separator.join(item.unit.text for item in self.items)


def select_context(
    items: Iterable[ContextItem],
    *,
    limits: Mapping[str, float],
) -> ContextSelection:
    """Greedily pack whole units under independent caller-named budgets."""

    maximum = {name: float(value) for name, value in limits.items()}
    if any(
        not name or not math.isfinite(value) or value < 0
        for name, value in maximum.items()
    ):
        raise ValueError("context limits must be named, finite, and non-negative")
    values = tuple(items)
    keys = [item.unit.ref.key for item in values]
    if len(keys) != len(set(keys)):
        raise ValueError("context artifact references must be unique")
    totals = {name: 0.0 for name in maximum}
    selected: list[ContextItem] = []
    trace: list[ContextSelectionTrace] = []
    for item in sorted(values, key=lambda value: (-value.score, value.unit.ref.key)):
        reasons = list(item.exclusion_reasons)
        if not item.eligible and not reasons:
            reasons.append("ineligible")
        for name, limit in maximum.items():
            if totals[name] + item.costs.get(name, 0.0) > limit:
                reasons.append(f"{name}_limit")
        if not reasons:
            selected.append(item)
            for name in totals:
                totals[name] += item.costs.get(name, 0.0)
        trace.append(
            ContextSelectionTrace(
                ref=item.unit.ref,
                included=not reasons,
                reasons=tuple(reasons),
            )
        )
    return ContextSelection(items=tuple(selected), totals=totals, trace=tuple(trace))


def select_context_diverse(
    items: Iterable[ContextItem],
    *,
    limits: Mapping[str, float],
    groups: Callable[[ContextItem], Iterable[Hashable]],
    maximum_per_group: Mapping[Hashable, int] | None = None,
    minimum_per_group: Mapping[Hashable, int] | None = None,
    marginal_gain: Callable[[ContextItem, tuple[ContextItem, ...]], float]
    | None = None,
    minimum_gain: float = 0.0,
) -> DiverseContextSelection:
    """Greedy constrained selection with caller-defined groups and utility."""

    maximum = {name: float(value) for name, value in limits.items()}
    if any(
        not name or not math.isfinite(value) or value < 0
        for name, value in maximum.items()
    ):
        raise ValueError("context limits must be named, finite, and non-negative")
    if not math.isfinite(minimum_gain):
        raise ValueError("minimum_gain must be finite")
    group_maximum = dict(maximum_per_group or {})
    group_minimum = dict(minimum_per_group or {})
    if any(value < 0 for value in (*group_maximum.values(), *group_minimum.values())):
        raise ValueError("group bounds must not be negative")
    values = tuple(items)
    keys = [item.unit.ref.key for item in values]
    if len(keys) != len(set(keys)):
        raise ValueError("context artifact references must be unique")
    item_groups = {
        item.unit.ref.key: tuple(sorted(set(groups(item)), key=repr)) for item in values
    }
    totals = {name: 0.0 for name in maximum}
    counts: dict[Hashable, int] = {}
    selected: list[ContextItem] = []
    gains: dict[tuple[str, str, str, str], float] = {}
    order: dict[tuple[str, str, str, str], int] = {}
    remaining = set(keys)
    items_by_key = {item.unit.ref.key: item for item in values}
    rounds: list[DiverseSelectionRound] = []

    def base_reasons(item: ContextItem) -> list[str]:
        reasons = list(item.exclusion_reasons)
        if not item.eligible and not reasons:
            reasons.append("ineligible")
        for name, limit in maximum.items():
            if totals[name] + item.costs.get(name, 0.0) > limit:
                reasons.append(f"{name}_limit")
        for group in item_groups[item.unit.ref.key]:
            if group in group_maximum and counts.get(group, 0) >= group_maximum[group]:
                reasons.append(f"group_limit:{group!r}")
        return reasons

    while remaining:
        unmet = {
            group
            for group, minimum in group_minimum.items()
            if counts.get(group, 0) < minimum
        }
        candidates: list[tuple[float, tuple[str, str, str, str], ContextItem]] = []
        fallback: list[tuple[float, tuple[str, str, str, str], ContextItem]] = []
        evaluations: list[DiverseCandidateEvaluation] = []
        for key in remaining:
            item = items_by_key[key]
            reasons = tuple(base_reasons(item))
            if reasons:
                evaluations.append(
                    DiverseCandidateEvaluation(
                        ref=item.unit.ref,
                        groups=item_groups[key],
                        marginal_gain=None,
                        reasons=reasons,
                    )
                )
                continue
            gain = float(
                marginal_gain(item, tuple(selected))
                if marginal_gain is not None
                else item.score
            )
            if not math.isfinite(gain):
                raise ValueError("marginal gains must be finite")
            evaluations.append(
                DiverseCandidateEvaluation(
                    ref=item.unit.ref,
                    groups=item_groups[key],
                    marginal_gain=gain,
                    reasons=(),
                )
            )
            row = (-gain, key, item)
            fallback.append(row)
            if not unmet or unmet & set(item_groups[key]):
                candidates.append(row)
        choices = candidates or fallback
        if not choices:
            rounds.append(
                DiverseSelectionRound(
                    iteration=len(rounds) + 1,
                    unmet_groups=tuple(sorted(unmet, key=repr)),
                    candidates=tuple(
                        sorted(evaluations, key=lambda value: value.ref.key)
                    ),
                    selected_ref=None,
                    stop_reason="no_feasible_candidate",
                )
            )
            break
        negative_gain, key, item = min(choices, key=lambda row: (row[0], row[1]))
        gain = -negative_gain
        if gain < minimum_gain:
            rounds.append(
                DiverseSelectionRound(
                    iteration=len(rounds) + 1,
                    unmet_groups=tuple(sorted(unmet, key=repr)),
                    candidates=tuple(
                        sorted(evaluations, key=lambda value: value.ref.key)
                    ),
                    selected_ref=None,
                    stop_reason="below_minimum_gain",
                )
            )
            break
        rounds.append(
            DiverseSelectionRound(
                iteration=len(rounds) + 1,
                unmet_groups=tuple(sorted(unmet, key=repr)),
                candidates=tuple(
                    sorted(evaluations, key=lambda value: value.ref.key)
                ),
                selected_ref=item.unit.ref,
            )
        )
        selected.append(item)
        remaining.remove(key)
        gains[key] = gain
        order[key] = len(selected)
        for name in totals:
            totals[name] += item.costs.get(name, 0.0)
        for group in item_groups[key]:
            counts[group] = counts.get(group, 0) + 1

    trace: list[DiverseSelectionTrace] = []
    for item in values:
        key = item.unit.ref.key
        included = key in order
        reasons = () if included else tuple(base_reasons(item) or ["not_selected"])
        gain = gains.get(key)
        if not included:
            gain = float(
                marginal_gain(item, tuple(selected))
                if marginal_gain is not None
                else item.score
            )
            if not math.isfinite(gain):
                raise ValueError("marginal gains must be finite")
        trace.append(
            DiverseSelectionTrace(
                ref=item.unit.ref,
                included=included,
                groups=item_groups[key],
                marginal_gain=gain,
                reasons=reasons,
                selection_order=order.get(key),
            )
        )
    unsatisfied = tuple(
        sorted(
            (
                group
                for group, minimum in group_minimum.items()
                if counts.get(group, 0) < minimum
            ),
            key=repr,
        )
    )
    return DiverseContextSelection(
        items=tuple(selected),
        totals=totals,
        group_counts=counts,
        unsatisfied_groups=unsatisfied,
        trace=tuple(trace),
        rounds=tuple(rounds),
    )
