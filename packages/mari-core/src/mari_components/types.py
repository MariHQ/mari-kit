"""Shared immutable values; none imply a database or application identity."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class SyncMode(str, Enum):
    INCREMENTAL = "incremental"
    FULL = "full"


@dataclass(frozen=True, slots=True)
class Principal:
    kind: str
    identifier: str

    def __post_init__(self) -> None:
        if not self.kind.strip() or not self.identifier.strip():
            raise ValueError("principal kind and identifier are required")


@dataclass(frozen=True, slots=True)
class DocumentACL:
    visibility: str = "connector_scope"
    principals: tuple[Principal, ...] = ()

    def __post_init__(self) -> None:
        if self.visibility not in {"public", "project", "connector_scope", "restricted"}:
            raise ValueError(f"unsupported visibility: {self.visibility}")


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    external_id: str
    title: str
    body: str
    revision: str = ""
    updated_at: str = ""
    source_url: str = ""
    acl: DocumentACL = field(default_factory=DocumentACL)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.external_id.strip():
            raise ValueError("document external_id is required")


@dataclass(frozen=True, slots=True)
class Upsert:
    document: KnowledgeDocument


@dataclass(frozen=True, slots=True)
class Tombstone:
    external_id: str
    reason: str = "provider_deleted"

    def __post_init__(self) -> None:
        if not self.external_id.strip():
            raise ValueError("tombstone external_id is required")


@dataclass(frozen=True, slots=True)
class PollRequest:
    mode: SyncMode = SyncMode.INCREMENTAL
    cursor: str | None = None
    checkpoint: str | None = None
    page_size: int = 100
    page_limit: int = 20

    def __post_init__(self) -> None:
        if self.page_size < 1 or self.page_limit < 1:
            raise ValueError("page_size and page_limit must be positive")


@dataclass(frozen=True, slots=True)
class PollPage:
    upserts: tuple[KnowledgeDocument, ...] = ()
    tombstones: tuple[Tombstone, ...] = ()
    next_cursor: str | None = None
    next_checkpoint: str | None = None
    snapshot_complete: bool = False
    provider_metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChangeHint:
    provider: str
    aggregate_key: str
    event_type: str
    external_id: str = ""
    revision: str = ""
    deleted: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.aggregate_key.strip() or not self.event_type.strip():
            raise ValueError("provider, aggregate_key, and event_type are required")


@dataclass(frozen=True, slots=True)
class Evidence:
    document_id: str
    revision: str = ""
    quote: str = ""
    start: int | None = None
    end: int | None = None


@dataclass(frozen=True, slots=True)
class FactCandidate:
    claim: str
    evidence: tuple[Evidence, ...]
    confidence: float
    qualifiers: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DecisionCandidate:
    statement: str
    evidence: tuple[Evidence, ...]
    confidence: float
    status: str = "proposed"


@dataclass(frozen=True, slots=True)
class GlossaryCandidate:
    term: str
    definition: str
    evidence: tuple[Evidence, ...]
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AnswerCandidate:
    question: str
    answer: str
    evidence: tuple[Evidence, ...]
    confidence: float


JsonValue = None | bool | int | float | str | Sequence["JsonValue"] | Mapping[str, "JsonValue"]
