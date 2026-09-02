"""Immutable results shared by verification algorithms."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Generic, TypeVar

from mari_components.types import Evidence

CandidateT = TypeVar("CandidateT")


@dataclass(frozen=True, slots=True, kw_only=True)
class VerificationScore:
    score: float
    groundedness: float
    completeness: float
    corroboration: float
    certainty: float
    evidence_valid: bool
    checks: Mapping[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        values = (
            self.score,
            self.groundedness,
            self.completeness,
            self.corroboration,
            self.certainty,
        )
        if any(not math.isfinite(value) or not 0 <= value <= 1 for value in values):
            raise ValueError("verification scores must be finite values in [0, 1]")
        object.__setattr__(self, "checks", MappingProxyType(dict(self.checks)))


@dataclass(frozen=True, slots=True, kw_only=True)
class ScoredAttempt(Generic[CandidateT]):
    index: int
    candidate: CandidateT
    score: float
    breakdown: VerificationScore | None = None

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("attempt index cannot be negative")
        if not math.isfinite(self.score):
            raise ValueError("attempt score must be finite")


@dataclass(frozen=True, slots=True, kw_only=True)
class AttemptFailure:
    index: int
    error_type: str
    message: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SelectionResult(Generic[CandidateT]):
    selected: CandidateT
    selected_index: int
    attempts: tuple[ScoredAttempt[CandidateT], ...]
    failures: tuple[AttemptFailure, ...] = ()
    stopped_early: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "attempts", tuple(self.attempts))
        object.__setattr__(self, "failures", tuple(self.failures))
        if not self.attempts:
            raise ValueError("selection result requires a scored attempt")
        if not any(row.index == self.selected_index for row in self.attempts):
            raise ValueError("selected index is not present in scored attempts")

    @property
    def selected_attempt(self) -> ScoredAttempt[CandidateT]:
        return next(row for row in self.attempts if row.index == self.selected_index)


@dataclass(frozen=True, slots=True, kw_only=True)
class ConsensusResult:
    claim: str
    verdict: str
    agreement: float
    evidence: tuple[Evidence, ...]
    votes: Mapping[str, float]
    assessments: tuple[object, ...]

    def __post_init__(self) -> None:
        if self.verdict not in {"supported", "contradicted", "uncertain"}:
            raise ValueError("consensus verdict is invalid")
        if not math.isfinite(self.agreement) or not 0 <= self.agreement <= 1:
            raise ValueError("consensus agreement must be in [0, 1]")
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "votes", MappingProxyType(dict(self.votes)))
        object.__setattr__(self, "assessments", tuple(self.assessments))
