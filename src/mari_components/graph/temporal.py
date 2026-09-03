"""Append-only bi-temporal fact operations."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Any

from mari_components.types import Evidence


def _aware(value: dt.datetime, field: str) -> dt.datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(dt.UTC)


@dataclass(frozen=True, slots=True, kw_only=True)
class TemporalFact:
    """One immutable assertion with valid-time and transaction-time intervals."""

    fact_id: str
    subject: str
    predicate: str
    object: Any
    valid_from: dt.datetime
    recorded_at: dt.datetime
    valid_to: dt.datetime | None = None
    retracted_at: dt.datetime | None = None
    evidence: tuple[Evidence, ...] = ()
    supersedes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            not self.fact_id.strip()
            or not self.subject.strip()
            or not self.predicate.strip()
        ):
            raise ValueError("fact ID, subject, and predicate are required")
        valid_from = _aware(self.valid_from, "valid_from")
        recorded_at = _aware(self.recorded_at, "recorded_at")
        valid_to = _aware(self.valid_to, "valid_to") if self.valid_to else None
        retracted_at = (
            _aware(self.retracted_at, "retracted_at") if self.retracted_at else None
        )
        if valid_to is not None and valid_to <= valid_from:
            raise ValueError("valid_to must be after valid_from")
        if retracted_at is not None and retracted_at <= recorded_at:
            raise ValueError("retracted_at must be after recorded_at")
        object.__setattr__(self, "valid_from", valid_from)
        object.__setattr__(self, "recorded_at", recorded_at)
        object.__setattr__(self, "valid_to", valid_to)
        object.__setattr__(self, "retracted_at", retracted_at)
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "supersedes", tuple(sorted(set(self.supersedes))))


def close_transaction(fact: TemporalFact, *, retracted_at: dt.datetime) -> TemporalFact:
    """Return a revision that closes when the system stopped believing a fact."""

    if fact.retracted_at is not None:
        raise ValueError("fact transaction interval is already closed")
    return replace(fact, retracted_at=retracted_at)


def query_temporal_facts(
    facts: Iterable[TemporalFact],
    *,
    at: dt.datetime,
    known_at: dt.datetime,
    subject: str | None = None,
    predicate: str | None = None,
) -> tuple[TemporalFact, ...]:
    """Query facts true at valid time and visible at transaction time.

    Intervals are half-open: ``start <= time < end``. Equal matches are ordered
    by identity so storage backends can reproduce the reference behavior.
    """

    valid_time = _aware(at, "at")
    transaction_time = _aware(known_at, "known_at")
    output = (
        fact
        for fact in facts
        if fact.valid_from <= valid_time
        and (fact.valid_to is None or valid_time < fact.valid_to)
        and fact.recorded_at <= transaction_time
        and (fact.retracted_at is None or transaction_time < fact.retracted_at)
        and (subject is None or fact.subject == subject)
        and (predicate is None or fact.predicate == predicate)
    )
    return tuple(sorted(output, key=lambda fact: fact.fact_id))
