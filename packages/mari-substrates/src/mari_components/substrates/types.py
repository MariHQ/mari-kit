"""Dependency-free values exchanged with knowledge substrates."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping


class Capability(StrEnum):
    SEARCH = "search"
    DOCUMENT_READ = "document.read"
    DOCUMENT_WRITE = "document.write"
    SOURCE_READ = "source.read"
    SOURCE_WRITE = "source.write"
    SOURCE_RUN = "source.run"


@dataclass(frozen=True, slots=True)
class SubstrateInfo:
    provider: str
    version: str
    capabilities: frozenset[Capability]
    healthy: bool
    detail: str = ""


@dataclass(frozen=True, slots=True)
class SearchRequest:
    query: str
    limit: int = 10
    offset: int = 0
    sources: tuple[str, ...] = ()
    tags: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    updated_after: dt.datetime | None = None

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("search query is required")
        if not 1 <= self.limit <= 100:
            raise ValueError("search limit must be between 1 and 100")
        if self.offset < 0:
            raise ValueError("search offset cannot be negative")
        if self.updated_after is not None and self.updated_after.tzinfo is None:
            raise ValueError("updated_after must be timezone-aware")


@dataclass(frozen=True, slots=True)
class SearchHit:
    document_id: str
    title: str
    content: str
    source: str
    url: str = ""
    updated_at: dt.datetime | None = None
    score: float | None = None
    citation_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TextSection:
    text: str
    url: str = ""
    heading: str = ""


@dataclass(frozen=True, slots=True)
class Document:
    external_id: str
    title: str
    source: str
    sections: tuple[TextSection, ...]
    updated_at: dt.datetime | None = None
    created_at: dt.datetime | None = None
    metadata: Mapping[str, str | tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.external_id or not self.title or not self.sections:
            raise ValueError("document id, title, and at least one section are required")
        for value in (self.updated_at, self.created_at):
            if value is not None and value.tzinfo is None:
                raise ValueError("document timestamps must be timezone-aware")


@dataclass(frozen=True, slots=True)
class UpsertResult:
    document_id: str
    created: bool


@dataclass(frozen=True, slots=True)
class Source:
    source_id: str
    name: str
    kind: str
    status: str
    credential_id: str = ""
    document_count: int | None = None
    last_run_at: dt.datetime | None = None
    error: str = ""
    configuration: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SourceRegistration:
    name: str
    kind: str
    configuration: Mapping[str, Any]
    credentials: Mapping[str, Any]
    refresh_seconds: int | None = None
    prune_seconds: int | None = None
    access: str = "public"
    groups: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not self.name or not self.kind:
            raise ValueError("source name and kind are required")
        if self.access not in {"public", "private", "sync"}:
            raise ValueError("source access must be public, private, or sync")
