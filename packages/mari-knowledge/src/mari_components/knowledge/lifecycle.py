"""Consistency rules for canonical documents and query projections."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from mari_components.documents import DocumentVersion


@dataclass(frozen=True, slots=True)
class ProjectionFields:
    source: str
    kind: str
    author: str
    author_initials: str


@dataclass(frozen=True, slots=True)
class DocumentPorts:
    append_canonical: Callable[[DocumentVersion], None]
    delete_canonical: Callable[[DocumentVersion], None]
    upsert_projection: Callable[[DocumentVersion, ProjectionFields], tuple[int, bool]]
    projected_versions: Callable[[int, list[int]], list[DocumentVersion]]
    delete_projections: Callable[[int, list[int]], None]


def upsert(version: DocumentVersion, fields: ProjectionFields, *, ports: DocumentPorts) -> tuple[int, bool]:
    """Write canonical content before its disposable/read-optimized projection.

    A projection failure cannot advance the connector checkpoint. Replaying the
    page is safe because canonical appends are content/revision idempotent.
    """
    ports.append_canonical(version)
    return ports.upsert_projection(version, fields)


def delete(project_id: int, document_ids: list[int], *, reason: str, actor: str,
           ports: DocumentPorts) -> None:
    """Record tombstones canonically before removing query projections."""
    if not document_ids:
        return
    versions = ports.projected_versions(project_id, document_ids)
    for current in versions:
        ports.delete_canonical(DocumentVersion(
            project_id=current.project_id, source_id=current.source_id,
            external_id=current.external_id, revision=current.revision,
            title=current.title, body=current.body, status="deleted",
            source_url=current.source_url, acl=current.acl, reason=reason, actor=actor,
        ))
    ports.delete_projections(project_id, document_ids)
