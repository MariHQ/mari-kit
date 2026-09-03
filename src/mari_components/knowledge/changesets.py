"""Cross-document edit validation with previews and inverse operations."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from mari_components.types import KnowledgeDocument

from .experience import KnowledgeEdit


@dataclass(frozen=True, slots=True, kw_only=True)
class PositionedKnowledgeEdit:
    edit: KnowledgeEdit
    start: int
    end: int


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeChangeEntry:
    document_id: str
    before_revision: str
    proposed_revision: str
    preview: str
    edits: tuple[PositionedKnowledgeEdit, ...]
    inverse_edits: tuple[KnowledgeEdit, ...]


class ChangesetIssueKind(StrEnum):
    UNKNOWN_DOCUMENT = "unknown_document"
    REVISION_MISMATCH = "revision_mismatch"
    ORIGINAL_NOT_UNIQUE = "original_not_unique"
    OVERLAPPING_EDITS = "overlapping_edits"


@dataclass(frozen=True, slots=True, kw_only=True)
class ChangesetIssue:
    kind: ChangesetIssueKind
    document_id: str
    edit_index: int


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeChangeset:
    changeset_id: str
    entries: tuple[KnowledgeChangeEntry, ...]
    issues: tuple[ChangesetIssue, ...]

    @property
    def valid(self) -> bool:
        return bool(self.entries) and not self.issues


def validate_knowledge_changeset(
    documents: Mapping[str, KnowledgeDocument], edits: Iterable[KnowledgeEdit]
) -> KnowledgeChangeset:
    """Validate a multi-document plan without committing or claiming atomicity."""

    values = tuple(edits)
    grouped: dict[str, list[tuple[int, KnowledgeEdit]]] = {}
    issues: list[ChangesetIssue] = []
    for index, edit in enumerate(values):
        document = documents.get(edit.document_id)
        if document is None:
            issues.append(
                ChangesetIssue(
                    kind=ChangesetIssueKind.UNKNOWN_DOCUMENT,
                    document_id=edit.document_id,
                    edit_index=index,
                )
            )
            continue
        if edit.source_revision != document.revision:
            issues.append(
                ChangesetIssue(
                    kind=ChangesetIssueKind.REVISION_MISMATCH,
                    document_id=edit.document_id,
                    edit_index=index,
                )
            )
            continue
        if document.body.count(edit.original) != 1:
            issues.append(
                ChangesetIssue(
                    kind=ChangesetIssueKind.ORIGINAL_NOT_UNIQUE,
                    document_id=edit.document_id,
                    edit_index=index,
                )
            )
            continue
        grouped.setdefault(edit.document_id, []).append((index, edit))

    entries: list[KnowledgeChangeEntry] = []
    for document_id, rows in sorted(grouped.items()):
        document = documents[document_id]
        positioned = tuple(
            sorted(
                (
                    PositionedKnowledgeEdit(
                        edit=edit,
                        start=document.body.index(edit.original),
                        end=document.body.index(edit.original) + len(edit.original),
                    )
                    for _, edit in rows
                ),
                key=lambda item: (item.start, item.end),
            )
        )
        overlapping = {
            right
            for left, right in zip(positioned, positioned[1:], strict=False)
            if right.start < left.end
        }
        if overlapping:
            for row in overlapping:
                original_index = next(index for index, edit in rows if edit == row.edit)
                issues.append(
                    ChangesetIssue(
                        kind=ChangesetIssueKind.OVERLAPPING_EDITS,
                        document_id=document_id,
                        edit_index=original_index,
                    )
                )
            continue
        preview = document.body
        for row in reversed(positioned):
            preview = preview[: row.start] + row.edit.replacement + preview[row.end :]
        proposed_revision = hashlib.sha256(preview.encode()).hexdigest()
        entries.append(
            KnowledgeChangeEntry(
                document_id=document_id,
                before_revision=document.revision,
                proposed_revision=proposed_revision,
                preview=preview,
                edits=positioned,
                inverse_edits=tuple(
                    KnowledgeEdit(
                        document_id=document_id,
                        source_revision=proposed_revision,
                        original=row.edit.replacement,
                        replacement=row.edit.original,
                        reason=f"inverse: {row.edit.reason}",
                    )
                    for row in positioned
                ),
            )
        )
    identity = repr(
        tuple(
            (entry.document_id, entry.before_revision, entry.proposed_revision)
            for entry in entries
        )
    ).encode()
    return KnowledgeChangeset(
        changeset_id=f"changeset:{hashlib.sha256(identity).hexdigest()[:20]}",
        entries=tuple(entries),
        issues=tuple(issues),
    )
