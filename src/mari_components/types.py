"""Canonical immutable values shared by Mari Components."""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class SyncMode(StrEnum):
    INCREMENTAL = "incremental"
    FULL = "full"


@dataclass(frozen=True, slots=True, kw_only=True)
class Principal:
    kind: str
    identifier: str

    def __post_init__(self) -> None:
        if not self.kind.strip() or not self.identifier.strip():
            raise ValueError("principal kind and identifier are required")
        object.__setattr__(self, "kind", self.kind.strip())
        object.__setattr__(self, "identifier", self.identifier.strip())


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentACL:
    """Provider-observed visibility metadata; hosts enforce authorization."""

    visibility: str = "connector_scope"
    principals: tuple[Principal, ...] = ()

    def __post_init__(self) -> None:
        if self.visibility not in {"public", "connector_scope", "restricted"}:
            raise ValueError(f"unsupported provider visibility: {self.visibility}")
        object.__setattr__(
            self,
            "principals",
            tuple(
                sorted(set(self.principals), key=lambda row: (row.kind, row.identifier))
            ),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeDocument:
    """One provider document at one immutable revision."""

    source_id: str
    external_id: str
    title: str
    body: str
    revision: str
    updated_at: str = ""
    source_url: str = ""
    acl: DocumentACL = field(default_factory=DocumentACL)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.external_id.strip():
            raise ValueError("document source_id and external_id are required")
        if not self.revision.strip():
            raise ValueError("document revision is required")
        if self.updated_at:
            try:
                parsed = dt.datetime.fromisoformat(
                    self.updated_at.strip().replace("Z", "+00:00")
                )
            except ValueError as error:
                raise ValueError(
                    "document updated_at must be an ISO 8601 timestamp"
                ) from error
            if parsed.tzinfo is None:
                raise ValueError("document updated_at must include a timezone")
            object.__setattr__(
                self,
                "updated_at",
                parsed.astimezone(dt.UTC).isoformat().replace("+00:00", "Z"),
            )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def document_id(self) -> str:
        return f"{self.source_id}/{self.external_id}"


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeSection:
    """A stable, content-versioned section inside one knowledge document."""

    document_id: str
    section_id: str
    title: str
    body: str
    revision: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if not self.document_id or not self.section_id or not self.revision:
            raise ValueError(
                "section document ID, section ID, and revision are required"
            )
        if self.start < 0 or self.end < self.start:
            raise ValueError("section span is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class Tombstone:
    source_id: str
    external_id: str
    reason: str = "provider_deleted"

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.external_id.strip():
            raise ValueError("tombstone source_id and external_id are required")

    @property
    def document_id(self) -> str:
        return f"{self.source_id}/{self.external_id}"


@dataclass(frozen=True, slots=True, kw_only=True)
class PollRequest:
    cursor: str | None = None
    checkpoint: str | None = None
    page_size: int = 100
    page_limit: int = 20

    def __post_init__(self) -> None:
        if self.page_size < 1 or self.page_limit < 1:
            raise ValueError("page_size and page_limit must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class PollPage:
    upserts: tuple[KnowledgeDocument, ...] = ()
    tombstones: tuple[Tombstone, ...] = ()
    next_cursor: str | None = None
    next_checkpoint: str | None = None
    snapshot_complete: bool = False
    provider_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "upserts", tuple(self.upserts))
        object.__setattr__(self, "tombstones", tuple(self.tombstones))
        object.__setattr__(
            self, "provider_metadata", MappingProxyType(dict(self.provider_metadata))
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ChangeHint:
    provider: str
    aggregate_key: str
    event_type: str
    external_id: str = ""
    revision: str = ""
    deleted: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (
            not self.provider.strip()
            or not self.aggregate_key.strip()
            or not self.event_type.strip()
        ):
            raise ValueError("provider, aggregate_key, and event_type are required")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True, kw_only=True)
class Evidence:
    document_id: str
    revision: str
    quote: str = ""
    start: int | None = None
    end: int | None = None
    section_id: str = ""
    section_revision: str = ""

    def __post_init__(self) -> None:
        if not self.document_id or not self.revision:
            raise ValueError("evidence document_id and revision are required")
        if (self.start is None) != (self.end is None):
            raise ValueError("evidence start and end must be supplied together")
        if bool(self.section_id) != bool(self.section_revision):
            raise ValueError(
                "evidence section ID and section revision must be supplied together"
            )
        if self.start is not None:
            end = self.end
            if end is None or self.start < 0 or end < self.start:
                raise ValueError("evidence span is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class FactCandidate:
    claim: str
    evidence: tuple[Evidence, ...]
    grounding_coverage: float
    qualifiers: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.claim.strip() or not self.evidence:
            raise ValueError("fact claim and evidence are required")
        if (
            not math.isfinite(self.grounding_coverage)
            or not 0 <= self.grounding_coverage <= 1
        ):
            raise ValueError("grounding_coverage must be between zero and one")
        object.__setattr__(self, "qualifiers", MappingProxyType(dict(self.qualifiers)))


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionCandidate:
    statement: str
    evidence: tuple[Evidence, ...]
    grounding_coverage: float
    status: str = "proposed"

    def __post_init__(self) -> None:
        if not self.statement.strip() or not self.evidence:
            raise ValueError("decision statement and evidence are required")
        if (
            not math.isfinite(self.grounding_coverage)
            or not 0 <= self.grounding_coverage <= 1
        ):
            raise ValueError("grounding_coverage must be between zero and one")


@dataclass(frozen=True, slots=True, kw_only=True)
class GlossaryCandidate:
    term: str
    definition: str
    evidence: tuple[Evidence, ...]
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.term.strip() or not self.definition.strip() or not self.evidence:
            raise ValueError("glossary term, definition, and evidence are required")


@dataclass(frozen=True, slots=True, kw_only=True)
class AnswerCandidate:
    question: str
    answer: str
    evidence: tuple[Evidence, ...]
    grounding_coverage: float

    def __post_init__(self) -> None:
        if not self.question.strip() or not self.answer.strip() or not self.evidence:
            raise ValueError("answer question, answer text, and evidence are required")
        if (
            not math.isfinite(self.grounding_coverage)
            or not 0 <= self.grounding_coverage <= 1
        ):
            raise ValueError("grounding_coverage must be between zero and one")


JsonValue = (
    None | bool | int | float | str | Sequence["JsonValue"] | Mapping[str, "JsonValue"]
)
