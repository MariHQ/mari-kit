"""Evidence-bearing temporal assertions and caller-selected update plans."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Generic, TypeVar

from mari_components.graph.temporal_tools import TimeInterval, close_interval

from .evidence import ArtifactEvidence

SubjectT = TypeVar("SubjectT", bound=Hashable)
PredicateT = TypeVar("PredicateT", bound=Hashable)
ValueT = TypeVar("ValueT")
ItemT = TypeVar("ItemT")


@dataclass(frozen=True, slots=True, kw_only=True)
class Assertion(Generic[SubjectT, PredicateT, ValueT]):
    assertion_id: str
    subject: SubjectT
    predicate: PredicateT
    value: ValueT
    recorded_at: dt.datetime
    valid_time: TimeInterval = TimeInterval()
    evidence: tuple[ArtifactEvidence, ...] = ()
    supersedes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.assertion_id.strip():
            raise ValueError("assertion ID is required")
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("recorded_at must be timezone-aware")
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "supersedes", tuple(sorted(set(self.supersedes))))
        if self.assertion_id in self.supersedes:
            raise ValueError("an assertion cannot supersede itself")


def group_assertions(
    assertions: Iterable[Assertion[SubjectT, PredicateT, ValueT]],
    *,
    key: Callable[[Assertion[SubjectT, PredicateT, ValueT]], Hashable] = lambda value: (
        value.subject,
        value.predicate,
    ),
) -> tuple[tuple[Hashable, tuple[Assertion[SubjectT, PredicateT, ValueT], ...]], ...]:
    """Group assertions by caller semantics with deterministic output."""

    grouped: dict[Hashable, list[Assertion[SubjectT, PredicateT, ValueT]]] = {}
    for assertion in assertions:
        grouped.setdefault(key(assertion), []).append(assertion)
    return tuple(
        (
            group_key,
            tuple(sorted(values, key=lambda value: value.assertion_id)),
        )
        for group_key, values in sorted(grouped.items(), key=lambda item: repr(item[0]))
    )


class AssertionUpdateKind(StrEnum):
    SUPERSEDE = "supersede"
    RETRACT = "retract"
    COEXIST = "coexist"
    DISPUTE = "dispute"


@dataclass(frozen=True, slots=True, kw_only=True)
class AssertionUpdatePlan:
    previous_id: str
    replacement_id: str | None
    kind: AssertionUpdateKind
    effective_at: dt.datetime
    close_previous_at: dt.datetime | None


def plan_assertion_update(
    previous: Assertion[Any, Any, Any],
    *,
    kind: AssertionUpdateKind,
    effective_at: dt.datetime,
    replacement: Assertion[Any, Any, Any] | None = None,
) -> AssertionUpdatePlan:
    """Return mechanics for a caller-selected assertion disposition."""

    if effective_at.tzinfo is None or effective_at.utcoffset() is None:
        raise ValueError("effective_at must be timezone-aware")
    if kind is AssertionUpdateKind.RETRACT and replacement is not None:
        raise ValueError("retraction does not take a replacement assertion")
    if kind is not AssertionUpdateKind.RETRACT and replacement is None:
        raise ValueError(f"{kind.value} requires a replacement assertion")
    close_at = (
        effective_at
        if kind in {AssertionUpdateKind.SUPERSEDE, AssertionUpdateKind.RETRACT}
        else None
    )
    if close_at is not None:
        close_interval(previous.valid_time, close_at)
    return AssertionUpdatePlan(
        previous_id=previous.assertion_id,
        replacement_id=None if replacement is None else replacement.assertion_id,
        kind=kind,
        effective_at=effective_at,
        close_previous_at=close_at,
    )


def valid_at(
    at_time: dt.datetime,
    *,
    interval: Callable[[ItemT], TimeInterval],
) -> Callable[[ItemT], bool]:
    """Build a reusable half-open valid-time predicate."""

    if at_time.tzinfo is None or at_time.utcoffset() is None:
        raise ValueError("at_time must be timezone-aware")

    def predicate(item: ItemT) -> bool:
        value = interval(item)
        return (value.start is None or value.start <= at_time) and (
            value.end is None or at_time < value.end
        )

    return predicate


def all_of(*predicates: Callable[[ItemT], bool]) -> Callable[[ItemT], bool]:
    return lambda item: all(predicate(item) for predicate in predicates)


def any_of(*predicates: Callable[[ItemT], bool]) -> Callable[[ItemT], bool]:
    return lambda item: any(predicate(item) for predicate in predicates)
