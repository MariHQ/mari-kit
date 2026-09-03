"""Structural validation for parser-neutral document values."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass

from . import (
    DocumentRegion,
    ParsedDocument,
    RegionEvidence,
    StructuredDocument,
    TableCell,
)
from .tables import normalize_table


@dataclass(frozen=True, slots=True, kw_only=True)
class StructureViolation:
    code: str
    subject: Hashable
    detail: str


@dataclass(frozen=True, slots=True, kw_only=True)
class StructureValidationReport:
    violations: tuple[StructureViolation, ...]

    @property
    def conforms(self) -> bool:
        return not self.violations


def _parent_violations(parents: dict[str, str]) -> list[StructureViolation]:
    output: list[StructureViolation] = []
    known = set(parents)
    for child, parent in parents.items():
        if parent and parent not in known:
            output.append(
                StructureViolation(
                    code="missing_parent", subject=child, detail=f"unknown parent {parent!r}"
                )
            )
            continue
        path: list[str] = []
        current = child
        while current and current in parents:
            if current in path:
                cycle = path[path.index(current) :] + [current]
                output.append(
                    StructureViolation(
                        code="parent_cycle",
                        subject=child,
                        detail=" -> ".join(cycle),
                    )
                )
                break
            path.append(current)
            current = parents[current]
    unique = {(value.code, value.subject, value.detail): value for value in output}
    return [unique[key] for key in sorted(unique, key=repr)]


def validate_parsed_document(
    document: ParsedDocument,
    *,
    source_length: int | None = None,
    require_parent_span_containment: bool = False,
) -> StructureValidationReport:
    """Check parent cycles, source bounds, and parent-span containment."""

    if source_length is not None and source_length < 0:
        raise ValueError("source_length must not be negative")
    by_id = {block.block_id: block for block in document.blocks}
    violations = _parent_violations(
        {block.block_id: block.parent_id for block in document.blocks}
    )
    for block in document.blocks:
        if (
            source_length is not None
            and block.end is not None
            and block.end > source_length
        ):
            violations.append(
                StructureViolation(
                    code="span_out_of_bounds",
                    subject=block.block_id,
                    detail=f"end {block.end} exceeds source length {source_length}",
                )
            )
        parent = by_id.get(block.parent_id)
        if (
            require_parent_span_containment
            and parent is not None
            and parent.start is not None
            and parent.end is not None
            and block.start is not None
            and block.end is not None
            and not (parent.start <= block.start and block.end <= parent.end)
        ):
            violations.append(
                StructureViolation(
                    code="outside_parent_span",
                    subject=block.block_id,
                    detail=f"span is outside parent {parent.block_id!r}",
                )
            )
    return StructureValidationReport(violations=tuple(violations))


def validate_structured_document(
    document: StructuredDocument,
) -> StructureValidationReport:
    """Check region hierarchy and table-cell topology."""

    violations = _parent_violations(
        {region.region_id: region.parent_id for region in document.regions}
    )
    for region in document.regions:
        normalized = normalize_table(region.cells)
        for row, column in normalized.conflicts:
            violations.append(
                StructureViolation(
                    code="overlapping_table_cells",
                    subject=region.region_id,
                    detail=f"multiple cells occupy ({row}, {column})",
                )
            )
    return StructureValidationReport(violations=tuple(violations))


@dataclass(frozen=True, slots=True, kw_only=True)
class RegionEvidenceResolution:
    evidence: RegionEvidence
    region_found: bool
    cell_found: bool | None
    issues: tuple[str, ...]
    region: DocumentRegion | None = None
    cell: TableCell | None = None
    candidate_cells: tuple[TableCell, ...] = ()
    text: str = ""

    @property
    def valid(self) -> bool:
        return not self.issues


def validate_region_evidence(
    evidence: RegionEvidence, document: StructuredDocument
) -> RegionEvidenceResolution:
    """Resolve exact document, revision, page, region, and optional cell."""

    issues: list[str] = []
    if evidence.document_id != document.document_id:
        issues.append("document_mismatch")
    if evidence.revision != document.revision:
        issues.append("revision_mismatch")
    region = next(
        (value for value in document.regions if value.region_id == evidence.region_id),
        None,
    )
    if region is None:
        issues.append("region_not_found")
        return RegionEvidenceResolution(
            evidence=evidence,
            region_found=False,
            cell_found=None,
            issues=tuple(issues),
            region=None,
        )
    if region.page != evidence.page:
        issues.append("page_mismatch")
    cell_found = None
    resolved_cell = None
    candidate_cells: tuple[TableCell, ...] = ()
    if evidence.cell is not None:
        row, column = evidence.cell
        candidate_cells = tuple(
            value
            for value in region.cells
            if value.row <= row < value.row + value.row_span
            and value.column <= column < value.column + value.column_span
        )
        cell_found = bool(candidate_cells)
        if not cell_found:
            issues.append("cell_not_found")
        elif len(candidate_cells) > 1:
            issues.append("ambiguous_cell")
        else:
            resolved_cell = next(iter(candidate_cells))
    return RegionEvidenceResolution(
        evidence=evidence,
        region_found=True,
        cell_found=cell_found,
        issues=tuple(issues),
        region=region,
        cell=resolved_cell,
        candidate_cells=candidate_cells,
        text=(
            resolved_cell.text
            if resolved_cell is not None
            else region.searchable_text
            if evidence.cell is None
            else ""
        ),
    )
