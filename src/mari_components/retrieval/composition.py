"""Typed handoffs from ranked IDs to artifact-neutral context material."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
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
