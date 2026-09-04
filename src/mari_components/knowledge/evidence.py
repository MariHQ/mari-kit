"""Artifact-neutral evidence resolution and exact-material validation."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from mari_components.json import freeze_json_mapping
from mari_components.references import (
    JsonPointer,
    LocatedEvidence,
    Locator,
    MediaTimeRange,
    PageRegion,
    RecordField,
    RevisionRef,
    TableCell,
    TextSpan,
)
from mari_components.types import Evidence

from .artifacts import ArtifactRef


@dataclass(frozen=True, slots=True, kw_only=True)
class ArtifactEvidence:
    ref: ArtifactRef
    quote: str = ""
    start: int | None = None
    end: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (self.start is None) != (self.end is None):
            raise ValueError("evidence start and end must be supplied together")
        if self.start is not None and (
            self.start < 0 or self.end is None or self.end < self.start
        ):
            raise ValueError("evidence span is invalid")
        object.__setattr__(self, "metadata", freeze_json_mapping(self.metadata))


@dataclass(frozen=True, slots=True, kw_only=True)
class LocatedEvidenceIssue:
    evidence: LocatedEvidence
    kind: EvidenceIssueKind
    detail: str


@dataclass(frozen=True, slots=True, kw_only=True)
class LocatedEvidenceReport:
    valid: tuple[LocatedEvidence, ...]
    issues: tuple[LocatedEvidenceIssue, ...]

    @property
    def accepted(self) -> bool:
        return bool(self.valid) and not self.issues


def document_evidence_ref(value: Evidence) -> ArtifactEvidence:
    """Adapt the document-specific compatibility type to generic evidence."""

    return ArtifactEvidence(
        ref=ArtifactRef(
            artifact_id=value.document_id,
            revision=value.revision,
            unit_id=value.section_id,
            namespace="document",
        ),
        quote=value.quote,
        start=value.start,
        end=value.end,
        metadata={"unit_revision": value.section_revision}
        if value.section_revision
        else {},
    )


class EvidenceIssueKind(StrEnum):
    NOT_VISIBLE = "not_visible"
    UNRESOLVED = "unresolved"
    INVALID_SPAN = "invalid_span"
    QUOTE_MISMATCH = "quote_mismatch"
    UNSUPPORTED_LOCATOR = "unsupported_locator"


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceIssue:
    evidence: ArtifactEvidence
    kind: EvidenceIssueKind
    detail: str


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceValidationReport:
    valid: tuple[ArtifactEvidence, ...]
    issues: tuple[EvidenceIssue, ...]

    @property
    def accepted(self) -> bool:
        return bool(self.valid) and not self.issues


def validate_artifact_evidence(
    evidence: Iterable[ArtifactEvidence],
    *,
    resolve_text: Callable[[ArtifactRef], str | None],
    visible_refs: Iterable[ArtifactRef] | None = None,
) -> EvidenceValidationReport:
    """Validate revision, visibility, span, and quote without judging sufficiency."""

    visible = None if visible_refs is None else {ref.key for ref in visible_refs}
    valid: list[ArtifactEvidence] = []
    issues: list[EvidenceIssue] = []
    for item in evidence:
        if visible is not None and item.ref.key not in visible:
            issues.append(
                EvidenceIssue(
                    evidence=item,
                    kind=EvidenceIssueKind.NOT_VISIBLE,
                    detail="artifact revision was not in the supplied material",
                )
            )
            continue
        text = resolve_text(item.ref)
        if text is None:
            issues.append(
                EvidenceIssue(
                    evidence=item,
                    kind=EvidenceIssueKind.UNRESOLVED,
                    detail="artifact revision could not be resolved",
                )
            )
            continue
        if item.start is not None:
            end = item.end
            if end is None or end > len(text):
                issues.append(
                    EvidenceIssue(
                        evidence=item,
                        kind=EvidenceIssueKind.INVALID_SPAN,
                        detail=f"span is outside material length {len(text)}",
                    )
                )
                continue
            if item.quote and text[item.start : end] != item.quote:
                issues.append(
                    EvidenceIssue(
                        evidence=item,
                        kind=EvidenceIssueKind.QUOTE_MISMATCH,
                        detail="quote does not match the supplied span",
                    )
                )
                continue
        elif item.quote and item.quote not in text:
            issues.append(
                EvidenceIssue(
                    evidence=item,
                    kind=EvidenceIssueKind.QUOTE_MISMATCH,
                    detail="quote does not occur in the supplied material",
                )
            )
            continue
        valid.append(item)
    return EvidenceValidationReport(valid=tuple(valid), issues=tuple(issues))


def _json_pointer(value: object, pointer: str) -> object:
    current = value
    if not pointer:
        return current
    for raw in pointer.split("/")[1:]:
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, Mapping):
            current = current[token]
        elif isinstance(current, Sequence) and not isinstance(
            current, (str, bytes, bytearray)
        ):
            current = current[int(token)]
        else:
            raise KeyError(token)
    return current


def _locate(material: object, locator: Locator | None) -> object:
    if locator is None:
        return material
    if isinstance(locator, TextSpan) and isinstance(material, str):
        if locator.end > len(material):
            raise IndexError(locator.end)
        return material[locator.start : locator.end]
    if isinstance(locator, JsonPointer):
        return _json_pointer(material, locator.pointer)
    if isinstance(locator, RecordField) and isinstance(material, Mapping):
        record = material[locator.record_id]
        if not isinstance(record, Mapping):
            raise TypeError("record is not a mapping")
        return record[locator.field]
    if isinstance(locator, TableCell) and isinstance(material, Sequence):
        row = material[locator.row]
        if not isinstance(row, Sequence) or isinstance(row, (str, bytes, bytearray)):
            raise TypeError("table row is not a sequence")
        return row[locator.column]
    if isinstance(locator, (PageRegion, MediaTimeRange)):
        raise NotImplementedError(type(locator).__name__)
    raise TypeError(type(locator).__name__)


def validate_located_evidence(
    evidence: Iterable[LocatedEvidence],
    *,
    resolve_material: Callable[[RevisionRef], object | None],
    visible_refs: Iterable[RevisionRef] | None = None,
    locate: Callable[[object, Locator | None], object] = _locate,
) -> LocatedEvidenceReport:
    """Resolve typed evidence while leaving visibility and storage to the caller."""

    visible = None if visible_refs is None else {ref.key for ref in visible_refs}
    valid: list[LocatedEvidence] = []
    issues: list[LocatedEvidenceIssue] = []
    for item in evidence:
        if visible is not None and item.ref.key not in visible:
            issues.append(
                LocatedEvidenceIssue(
                    evidence=item,
                    kind=EvidenceIssueKind.NOT_VISIBLE,
                    detail="artifact revision was not in the supplied material",
                )
            )
            continue
        material = resolve_material(item.ref)
        if material is None:
            issues.append(
                LocatedEvidenceIssue(
                    evidence=item,
                    kind=EvidenceIssueKind.UNRESOLVED,
                    detail="artifact revision could not be resolved",
                )
            )
            continue
        try:
            selected = locate(material, item.locator)
        except NotImplementedError:
            issues.append(
                LocatedEvidenceIssue(
                    evidence=item,
                    kind=EvidenceIssueKind.UNSUPPORTED_LOCATOR,
                    detail=f"{type(item.locator).__name__} requires a caller locator",
                )
            )
            continue
        except (IndexError, KeyError, TypeError, ValueError) as error:
            issues.append(
                LocatedEvidenceIssue(
                    evidence=item,
                    kind=EvidenceIssueKind.INVALID_SPAN,
                    detail=f"locator did not resolve: {error}",
                )
            )
            continue
        if item.quote and str(selected) != item.quote:
            issues.append(
                LocatedEvidenceIssue(
                    evidence=item,
                    kind=EvidenceIssueKind.QUOTE_MISMATCH,
                    detail="resolved material does not match the supplied quote",
                )
            )
            continue
        valid.append(item)
    return LocatedEvidenceReport(valid=tuple(valid), issues=tuple(issues))
