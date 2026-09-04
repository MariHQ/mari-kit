"""Structural identities and locators shared across knowledge subsystems."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias


@dataclass(frozen=True, slots=True, kw_only=True)
class ScopeRef:
    """Application-owned isolation boundary."""

    tenant: str
    space: str = "default"

    def __post_init__(self) -> None:
        tenant = self.tenant.strip()
        space = self.space.strip()
        if not tenant or not space:
            raise ValueError("scope tenant and space are required")
        object.__setattr__(self, "tenant", tenant)
        object.__setattr__(self, "space", space)

    @property
    def key(self) -> tuple[str, str]:
        return self.tenant, self.space


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectRef:
    """An object identity independent of any particular storage encoding."""

    namespace: str
    object_id: str
    scope: ScopeRef | None = None

    def __post_init__(self) -> None:
        namespace = self.namespace.strip()
        object_id = self.object_id.strip()
        if not namespace or not object_id:
            raise ValueError("object namespace and ID are required")
        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "object_id", object_id)

    @property
    def key(self) -> tuple[str, str, str, str]:
        tenant, space = self.scope.key if self.scope else ("", "")
        return tenant, space, self.namespace, self.object_id


@dataclass(frozen=True, slots=True, kw_only=True)
class RevisionRef:
    """One immutable revision, optionally narrowed to a stable unit."""

    object: ObjectRef
    revision: str
    unit_id: str = ""

    def __post_init__(self) -> None:
        revision = self.revision.strip()
        if not revision:
            raise ValueError("revision is required")
        object.__setattr__(self, "revision", revision)
        object.__setattr__(self, "unit_id", self.unit_id.strip())

    @property
    def key(self) -> tuple[str, str, str, str, str, str]:
        return (*self.object.key, self.revision, self.unit_id)


@dataclass(frozen=True, slots=True, kw_only=True)
class TextSpan:
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError("text span is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class JsonPointer:
    pointer: str

    def __post_init__(self) -> None:
        if self.pointer and not self.pointer.startswith("/"):
            raise ValueError("JSON pointer must be empty or start with '/'")


@dataclass(frozen=True, slots=True, kw_only=True)
class RecordField:
    record_id: str
    field: str

    def __post_init__(self) -> None:
        if not self.record_id.strip() or not self.field.strip():
            raise ValueError("record ID and field are required")


@dataclass(frozen=True, slots=True, kw_only=True)
class TableCell:
    row: int
    column: int

    def __post_init__(self) -> None:
        if self.row < 0 or self.column < 0:
            raise ValueError("table cell coordinates must be non-negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class PageRegion:
    page: int
    bounding_box: tuple[float, float, float, float]

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page must be positive")
        left, top, right, bottom = self.bounding_box
        if right < left or bottom < top:
            raise ValueError("page region bounding box is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class MediaTimeRange:
    start_seconds: float
    end_seconds: float

    def __post_init__(self) -> None:
        if self.start_seconds < 0 or self.end_seconds < self.start_seconds:
            raise ValueError("media time range is invalid")


Locator: TypeAlias = (
    TextSpan | JsonPointer | RecordField | TableCell | PageRegion | MediaTimeRange
)


@dataclass(frozen=True, slots=True, kw_only=True)
class LocatedEvidence:
    """Evidence against any revision-addressed material."""

    ref: RevisionRef
    locator: Locator | None = None
    quote: str = ""
