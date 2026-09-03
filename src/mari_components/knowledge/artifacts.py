"""Generic immutable envelopes for governed knowledge artifacts."""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Generic, TypeVar

from mari_components.types import Evidence

PayloadT = TypeVar("PayloadT")


class ReviewState(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeScope:
    tenant: str
    space: str = "default"

    def __post_init__(self) -> None:
        if not self.tenant.strip() or not self.space.strip():
            raise ValueError("scope tenant and space are required")


@dataclass(frozen=True, slots=True, kw_only=True)
class Activity:
    identifier: str
    implementation: str
    configuration: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.identifier.strip() or not self.implementation.strip():
            raise ValueError("activity identifier and implementation are required")
        object.__setattr__(
            self, "configuration", MappingProxyType(dict(self.configuration))
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeArtifact(Generic[PayloadT]):
    """Stable identity plus one immutable, provenance-bearing revision."""

    artifact_id: str
    revision: str
    value: PayloadT
    scope: KnowledgeScope
    recorded_at: dt.datetime
    generated_by: Activity
    evidence: tuple[Evidence, ...] = ()
    derived_from: tuple[str, ...] = ()
    supersedes: tuple[str, ...] = ()
    valid_from: dt.datetime | None = None
    valid_to: dt.datetime | None = None
    review_state: ReviewState = ReviewState.PROPOSED

    def __post_init__(self) -> None:
        if not self.artifact_id.strip() or not self.revision.strip():
            raise ValueError("artifact ID and revision are required")
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("recorded_at must be timezone-aware")
        if self.valid_from and (
            self.valid_from.tzinfo is None or self.valid_from.utcoffset() is None
        ):
            raise ValueError("valid_from must be timezone-aware")
        if self.valid_to and (
            self.valid_to.tzinfo is None or self.valid_to.utcoffset() is None
        ):
            raise ValueError("valid_to must be timezone-aware")
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be after valid_from")
        predecessor = f"{self.artifact_id}@{self.revision}"
        if predecessor in self.supersedes:
            raise ValueError("an artifact revision cannot supersede itself")
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "derived_from", tuple(sorted(set(self.derived_from))))
        object.__setattr__(self, "supersedes", tuple(sorted(set(self.supersedes))))
