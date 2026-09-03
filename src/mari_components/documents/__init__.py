"""Canonical structured-document and code-graph values."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True, slots=True, kw_only=True)
class ParsedBlock:
    """Format-neutral parsed material with stable source coordinates."""

    block_id: str
    kind: str
    text: str
    parent_id: str = ""
    start: int | None = None
    end: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.block_id.strip() or not self.kind.strip():
            raise ValueError("parsed block ID and kind are required")
        if (self.start is None) != (self.end is None):
            raise ValueError("parsed block start and end must be supplied together")
        if self.start is not None and (
            self.start < 0 or self.end is None or self.end < self.start
        ):
            raise ValueError("parsed block span is invalid")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True, kw_only=True)
class ParsedDocument:
    artifact_id: str
    revision: str
    media_type: str
    blocks: tuple[ParsedBlock, ...]

    def __post_init__(self) -> None:
        if not self.artifact_id.strip() or not self.revision.strip():
            raise ValueError("parsed document artifact ID and revision are required")
        if not self.media_type.strip():
            raise ValueError("parsed document media type is required")
        ids = [block.block_id for block in self.blocks]
        if len(ids) != len(set(ids)):
            raise ValueError("parsed block IDs must be unique")
        known = set(ids)
        if any(
            block.parent_id and block.parent_id not in known for block in self.blocks
        ):
            raise ValueError("parsed block parents must reference known blocks")
        object.__setattr__(self, "blocks", tuple(self.blocks))


@dataclass(frozen=True, slots=True, kw_only=True)
class BoundingBox:
    left: float
    top: float
    right: float
    bottom: float

    def __post_init__(self) -> None:
        if (
            self.left < 0
            or self.top < 0
            or self.right <= self.left
            or self.bottom <= self.top
        ):
            raise ValueError(
                "bounding box must have positive area and non-negative origin"
            )


class RegionKind(StrEnum):
    TEXT = "text"
    HEADING = "heading"
    TABLE = "table"
    FIGURE = "figure"
    FORMULA = "formula"
    CODE = "code"
    HEADER = "header"
    FOOTER = "footer"


@dataclass(frozen=True, slots=True, kw_only=True)
class TableCell:
    row: int
    column: int
    text: str
    row_span: int = 1
    column_span: int = 1
    header: bool = False

    def __post_init__(self) -> None:
        if self.row < 0 or self.column < 0 or self.row_span < 1 or self.column_span < 1:
            raise ValueError("table cell coordinates and spans are invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentRegion:
    region_id: str
    page: int
    kind: RegionKind
    bbox: BoundingBox
    text: str = ""
    cells: tuple[TableCell, ...] = ()
    parent_id: str = ""
    image_ref: str = ""

    def __post_init__(self) -> None:
        if not self.region_id.strip() or self.page < 1:
            raise ValueError("region ID and positive page number are required")
        if self.cells and self.kind is not RegionKind.TABLE:
            raise ValueError("only table regions may contain cells")
        object.__setattr__(self, "cells", tuple(self.cells))

    @property
    def searchable_text(self) -> str:
        if self.text:
            return self.text
        return "\n".join(cell.text for cell in self.cells if cell.text)


@dataclass(frozen=True, slots=True, kw_only=True)
class RegionRepresentation:
    region_id: str
    kind: str
    content: str
    model: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class RegionEvidence:
    document_id: str
    revision: str
    region_id: str
    page: int
    cell: tuple[int, int] | None = None

    def __post_init__(self) -> None:
        if (
            not self.document_id
            or not self.revision
            or not self.region_id
            or self.page < 1
        ):
            raise ValueError(
                "region evidence requires document, revision, region, and page"
            )
        if self.cell is not None and min(self.cell) < 0:
            raise ValueError("cell coordinates must not be negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class StructuredDocument:
    document_id: str
    revision: str
    regions: tuple[DocumentRegion, ...]
    representations: tuple[RegionRepresentation, ...] = ()

    def __post_init__(self) -> None:
        if not self.document_id or not self.revision:
            raise ValueError("document ID and revision are required")
        ids = [region.region_id for region in self.regions]
        if len(ids) != len(set(ids)):
            raise ValueError("region IDs must be unique")
        known = set(ids)
        if any(value.region_id not in known for value in self.representations):
            raise ValueError("representations must reference a document region")
        object.__setattr__(self, "regions", tuple(self.regions))
        object.__setattr__(self, "representations", tuple(self.representations))


class CodeSymbolKind(StrEnum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    ROUTE = "route"


class CodeEdgeKind(StrEnum):
    DEFINES = "defines"
    REFERENCES = "references"
    CALLS = "calls"
    IMPORTS = "imports"
    INHERITS = "inherits"
    IMPLEMENTS = "implements"


@dataclass(frozen=True, slots=True, kw_only=True)
class CodeSymbol:
    symbol_id: str
    repository: str
    revision: str
    language: str
    qualified_name: str
    kind: CodeSymbolKind
    start_line: int
    end_line: int

    def __post_init__(self) -> None:
        if not all(
            (
                self.symbol_id,
                self.repository,
                self.revision,
                self.language,
                self.qualified_name,
            )
        ):
            raise ValueError("code symbol identity fields are required")
        if self.start_line < 1 or self.end_line < self.start_line:
            raise ValueError("code symbol line span is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class CodeEdge:
    source_id: str
    target_id: str
    kind: CodeEdgeKind


def impacted_symbols(
    changed_ids: Iterable[str], edges: Iterable[CodeEdge], *, max_depth: int = 3
) -> tuple[str, ...]:
    """Traverse reverse structural dependencies in stable breadth-first order."""

    if max_depth < 0:
        raise ValueError("max_depth must not be negative")
    reverse: dict[str, list[str]] = {}
    for edge in edges:
        reverse.setdefault(edge.target_id, []).append(edge.source_id)
    seen = set(changed_ids)
    queue = deque((value, 0) for value in sorted(seen))
    result: list[str] = []
    while queue:
        target, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for source in sorted(reverse.get(target, ())):
            if source not in seen:
                seen.add(source)
                result.append(source)
                queue.append((source, depth + 1))
    return tuple(result)
