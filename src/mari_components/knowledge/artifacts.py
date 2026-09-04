"""Generic immutable envelopes for governed knowledge artifacts."""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Generic, TypeVar

from mari_components.json import freeze_json_mapping, freeze_json_value
from mari_components.references import LocatedEvidence, ObjectRef, RevisionRef, ScopeRef
from mari_components.types import Evidence

PayloadT = TypeVar("PayloadT")


@dataclass(frozen=True, slots=True, kw_only=True)
class ArtifactRef:
    """Application-owned artifact identity at one immutable revision."""

    artifact_id: str
    revision: str
    unit_id: str = ""
    namespace: str = ""
    scope: ScopeRef | None = None

    def __post_init__(self) -> None:
        if not self.artifact_id.strip() or not self.revision.strip():
            raise ValueError("artifact ID and revision are required")

    @property
    def key(self) -> tuple[str, str, str, str, str, str]:
        tenant, space = self.scope.key if self.scope else ("", "")
        return (
            tenant,
            space,
            self.namespace,
            self.artifact_id,
            self.revision,
            self.unit_id,
        )

    def to_revision_ref(self, *, scope: ScopeRef | None = None) -> RevisionRef:
        return RevisionRef(
            object=ObjectRef(
                namespace=self.namespace or "artifact",
                object_id=self.artifact_id,
                scope=scope or self.scope,
            ),
            revision=self.revision,
            unit_id=self.unit_id,
        )


class ReviewState(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"


KnowledgeScope = ScopeRef


@dataclass(frozen=True, slots=True, kw_only=True)
class Activity:
    identifier: str
    implementation: str
    configuration: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.identifier.strip() or not self.implementation.strip():
            raise ValueError("activity identifier and implementation are required")
        object.__setattr__(
            self, "configuration", freeze_json_mapping(self.configuration)
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeArtifact(Generic[PayloadT]):
    """Stable identity plus one frozen, provenance-bearing revision envelope."""

    artifact_id: str
    revision: str
    value: PayloadT
    scope: KnowledgeScope
    recorded_at: dt.datetime
    generated_by: Activity
    evidence: tuple[Evidence | LocatedEvidence, ...] = ()
    derived_from: tuple[str | RevisionRef, ...] = ()
    supersedes: tuple[str | RevisionRef, ...] = ()
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
        if self.value is None or isinstance(
            self.value, (str, int, float, bool, Mapping, tuple, list, set, frozenset)
        ):
            object.__setattr__(self, "value", freeze_json_value(self.value))
        predecessor = f"{self.artifact_id}@{self.revision}"
        own_ref = self.ref
        if predecessor in self.supersedes or own_ref in self.supersedes:
            raise ValueError("an artifact revision cannot supersede itself")
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(
            self,
            "derived_from",
            tuple(sorted(set(self.derived_from), key=_reference_sort_key)),
        )
        object.__setattr__(
            self,
            "supersedes",
            tuple(sorted(set(self.supersedes), key=_reference_sort_key)),
        )

    @property
    def ref(self) -> RevisionRef:
        return RevisionRef(
            object=ObjectRef(
                namespace="artifact", object_id=self.artifact_id, scope=self.scope
            ),
            revision=self.revision,
        )


def _reference_sort_key(value: str | RevisionRef) -> tuple[str, ...]:
    return (value,) if isinstance(value, str) else value.key
