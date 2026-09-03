"""Composable filtering and cross-stage candidate decision traces."""

from __future__ import annotations

import math
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Generic, TypeVar

from .composition import DiverseContextSelection

ItemT = TypeVar("ItemT")


@dataclass(frozen=True, slots=True, kw_only=True)
class FilterPredicate(Generic[ItemT]):
    reason: str
    accepts: Callable[[ItemT], bool]

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("filter reason is required")


@dataclass(frozen=True, slots=True, kw_only=True)
class FilterDecision(Generic[ItemT]):
    item: ItemT
    accepted: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class FilterResult(Generic[ItemT]):
    accepted: tuple[ItemT, ...]
    rejected: tuple[ItemT, ...]
    decisions: tuple[FilterDecision[ItemT], ...]


def filter_with_reasons(
    items: Iterable[ItemT],
    *,
    predicates: Iterable[FilterPredicate[ItemT]],
) -> FilterResult[ItemT]:
    """Apply every caller predicate and retain all failed reason labels."""

    checks = tuple(predicates)
    decisions: list[FilterDecision[ItemT]] = []
    accepted: list[ItemT] = []
    rejected: list[ItemT] = []
    for item in items:
        reasons = tuple(check.reason for check in checks if not check.accepts(item))
        decision = FilterDecision(item=item, accepted=not reasons, reasons=reasons)
        decisions.append(decision)
        (accepted if decision.accepted else rejected).append(item)
    return FilterResult(
        accepted=tuple(accepted),
        rejected=tuple(rejected),
        decisions=tuple(decisions),
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class CandidateDecision:
    candidate_id: Hashable
    stage: str
    included: bool
    reasons: tuple[str, ...] = ()
    parent_ids: tuple[Hashable, ...] = ()
    scores: Mapping[str, float] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.stage.strip():
            raise ValueError("candidate decision stage is required")
        score_values = {name: float(value) for name, value in self.scores.items()}
        if any(
            not name or not math.isfinite(value) for name, value in score_values.items()
        ):
            raise ValueError("candidate score contributions must be named and finite")
        object.__setattr__(self, "reasons", tuple(dict.fromkeys(self.reasons)))
        object.__setattr__(self, "parent_ids", tuple(dict.fromkeys(self.parent_ids)))
        object.__setattr__(self, "scores", MappingProxyType(score_values))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True, kw_only=True)
class CandidateHistory:
    decisions: tuple[CandidateDecision, ...] = ()

    def append(self, *decisions: CandidateDecision) -> CandidateHistory:
        """Append decisions without defining or validating a stage order."""

        return CandidateHistory(decisions=(*self.decisions, *decisions))

    def for_candidate(self, candidate_id: Hashable) -> tuple[CandidateDecision, ...]:
        return tuple(
            decision
            for decision in self.decisions
            if decision.candidate_id == candidate_id
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class CandidateHistoryDiagnostics:
    identity_aliases: tuple[tuple[Hashable, ...], ...]
    conflicting_stage_decisions: tuple[tuple[Hashable, str], ...]
    missing_parent_ids: tuple[Hashable, ...]


def diagnose_candidate_history(
    history: CandidateHistory,
    *,
    canonicalize: Callable[[Hashable], Hashable] = lambda value: value,
    external_parent_ids: Iterable[Hashable] = (),
) -> CandidateHistoryDiagnostics:
    """Find identity aliases, stage conflicts, and unresolved parent IDs."""

    aliases: dict[Hashable, set[Hashable]] = {}
    by_stage: dict[tuple[Hashable, str], list[CandidateDecision]] = {}
    known: set[Hashable] = set()
    for decision in history.decisions:
        canonical = canonicalize(decision.candidate_id)
        known.add(canonical)
        aliases.setdefault(canonical, set()).add(decision.candidate_id)
        by_stage.setdefault((canonical, decision.stage), []).append(decision)
    external = {canonicalize(value) for value in external_parent_ids}
    missing = {
        parent
        for decision in history.decisions
        for parent in decision.parent_ids
        if canonicalize(parent) not in known | external
    }
    conflicts = tuple(
        sorted(
            (
                key
                for key, decisions in by_stage.items()
                if len(
                    {
                        (decision.included, decision.reasons)
                        for decision in decisions
                    }
                )
                > 1
            ),
            key=lambda value: (repr(value[0]), value[1]),
        )
    )
    return CandidateHistoryDiagnostics(
        identity_aliases=tuple(
            tuple(sorted(values, key=repr))
            for _, values in sorted(aliases.items(), key=lambda item: repr(item[0]))
            if len(values) > 1
        ),
        conflicting_stage_decisions=conflicts,
        missing_parent_ids=tuple(sorted(missing, key=repr)),
    )


def decisions_from_filter(
    result: FilterResult[ItemT],
    *,
    stage: str,
    identity: Callable[[ItemT], Hashable],
) -> tuple[CandidateDecision, ...]:
    """Convert reasoned filter output without prescribing a stage vocabulary."""

    return tuple(
        CandidateDecision(
            candidate_id=identity(decision.item),
            stage=stage,
            included=decision.accepted,
            reasons=decision.reasons,
        )
        for decision in result.decisions
    )


def decisions_from_context(
    result: DiverseContextSelection, *, stage: str
) -> tuple[CandidateDecision, ...]:
    """Convert a diverse-selection trace while retaining gains and groups."""

    return tuple(
        CandidateDecision(
            candidate_id=entry.ref,
            stage=stage,
            included=entry.included,
            reasons=entry.reasons,
            scores=(
                {}
                if entry.marginal_gain is None
                else {"marginal_gain": entry.marginal_gain}
            ),
            metadata={
                "groups": entry.groups,
                "selection_order": entry.selection_order,
            },
        )
        for entry in result.trace
    )
