"""Reference in-memory store for revision and point-in-time conformance."""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from mari_components.knowledge.artifacts import KnowledgeArtifact, KnowledgeScope
from mari_components.references import RevisionRef, ScopeRef
from mari_components.types import KnowledgeDocument


class RevisionConflict(RuntimeError):
    """The caller's expected current revision did not match storage."""


@dataclass(frozen=True, slots=True, kw_only=True)
class StoreCapabilities:
    compare_and_swap: bool
    point_in_time_reads: bool
    history: bool
    scope_isolation: bool


@runtime_checkable
class ArtifactStore(Protocol):
    """Observable revision-store semantics for application adapters."""

    @property
    def capabilities(self) -> StoreCapabilities: ...

    def commit(
        self,
        artifact: KnowledgeArtifact[Any],
        *,
        expected_revision: str | None,
    ) -> None: ...

    def get(
        self, artifact_id: str, *, scope: KnowledgeScope
    ) -> KnowledgeArtifact[Any] | None: ...

    def at_time(
        self,
        artifact_id: str,
        *,
        scope: KnowledgeScope,
        known_at: dt.datetime,
    ) -> KnowledgeArtifact[Any] | None: ...

    def history(
        self, artifact_id: str, *, scope: KnowledgeScope
    ) -> tuple[KnowledgeArtifact[Any], ...]: ...


@runtime_checkable
class DocumentStore(Protocol):
    """Canonical document revisions addressed by structural source identity."""

    @property
    def capabilities(self) -> StoreCapabilities: ...

    def commit(
        self,
        document: KnowledgeDocument,
        *,
        scope: ScopeRef,
        expected_revision: str | None,
    ) -> None: ...

    def get(
        self, source_id: str, external_id: str, *, scope: ScopeRef
    ) -> KnowledgeDocument | None: ...

    def resolve(self, ref: RevisionRef) -> KnowledgeDocument | None: ...

    def history(
        self, source_id: str, external_id: str, *, scope: ScopeRef
    ) -> tuple[KnowledgeDocument, ...]: ...


class InMemoryDocumentStore:
    """Reference document-store semantics for adapter conformance."""

    def __init__(self) -> None:
        self._revisions: dict[tuple[str, str, str, str], list[KnowledgeDocument]] = (
            defaultdict(list)
        )

    @property
    def capabilities(self) -> StoreCapabilities:
        return StoreCapabilities(
            compare_and_swap=True,
            point_in_time_reads=False,
            history=True,
            scope_isolation=True,
        )

    @staticmethod
    def _key(
        scope: ScopeRef, source_id: str, external_id: str
    ) -> tuple[str, str, str, str]:
        return scope.tenant, scope.space, source_id, external_id

    def commit(
        self,
        document: KnowledgeDocument,
        *,
        scope: ScopeRef,
        expected_revision: str | None,
    ) -> None:
        revisions = self._revisions[
            self._key(scope, document.source_id, document.external_id)
        ]
        current = revisions[-1].revision if revisions else None
        if current != expected_revision:
            raise RevisionConflict(f"expected {expected_revision!r}, found {current!r}")
        if any(value.revision == document.revision for value in revisions):
            raise ValueError("document revision already exists")
        revisions.append(document)

    def get(
        self, source_id: str, external_id: str, *, scope: ScopeRef
    ) -> KnowledgeDocument | None:
        revisions = self._revisions.get(self._key(scope, source_id, external_id), ())
        return revisions[-1] if revisions else None

    def resolve(self, ref: RevisionRef) -> KnowledgeDocument | None:
        scope = ref.object.scope
        if scope is None:
            raise ValueError("document resolution requires a scoped reference")
        revisions = self._revisions.get(
            self._key(scope, ref.object.namespace, ref.object.object_id), ()
        )
        return next(
            (value for value in revisions if value.revision == ref.revision), None
        )

    def history(
        self, source_id: str, external_id: str, *, scope: ScopeRef
    ) -> tuple[KnowledgeDocument, ...]:
        return tuple(self._revisions.get(self._key(scope, source_id, external_id), ()))


class InMemoryArtifactStore:
    """Minimal reference semantics; production adapters run against the same cases."""

    def __init__(self) -> None:
        self._revisions: dict[tuple[str, str, str], list[KnowledgeArtifact[Any]]] = (
            defaultdict(list)
        )

    @property
    def capabilities(self) -> StoreCapabilities:
        return StoreCapabilities(
            compare_and_swap=True,
            point_in_time_reads=True,
            history=True,
            scope_isolation=True,
        )

    @staticmethod
    def _key(scope: KnowledgeScope, artifact_id: str) -> tuple[str, str, str]:
        return scope.tenant, scope.space, artifact_id

    def commit(
        self,
        artifact: KnowledgeArtifact[Any],
        *,
        expected_revision: str | None,
    ) -> None:
        key = self._key(artifact.scope, artifact.artifact_id)
        revisions = self._revisions[key]
        current = revisions[-1].revision if revisions else None
        if current != expected_revision:
            raise RevisionConflict(f"expected {expected_revision!r}, found {current!r}")
        if any(value.revision == artifact.revision for value in revisions):
            raise ValueError("artifact revision already exists")
        current_ref = revisions[-1].ref if revisions else None
        legacy_current = f"{artifact.artifact_id}@{current}"
        if revisions and not (
            legacy_current in artifact.supersedes or current_ref in artifact.supersedes
        ):
            raise ValueError(
                "a new revision must explicitly supersede the current revision"
            )
        revisions.append(artifact)

    def get(
        self, artifact_id: str, *, scope: KnowledgeScope
    ) -> KnowledgeArtifact[Any] | None:
        revisions = self._revisions.get(self._key(scope, artifact_id), ())
        return revisions[-1] if revisions else None

    def at_time(
        self,
        artifact_id: str,
        *,
        scope: KnowledgeScope,
        known_at: dt.datetime,
    ) -> KnowledgeArtifact[Any] | None:
        if known_at.tzinfo is None or known_at.utcoffset() is None:
            raise ValueError("known_at must be timezone-aware")
        revisions = self._revisions.get(self._key(scope, artifact_id), ())
        visible = [
            (position, value)
            for position, value in enumerate(revisions)
            if value.recorded_at <= known_at
        ]
        return (
            max(visible, key=lambda row: (row[1].recorded_at, row[0]))[1]
            if visible
            else None
        )

    def history(
        self, artifact_id: str, *, scope: KnowledgeScope
    ) -> tuple[KnowledgeArtifact[Any], ...]:
        return tuple(self._revisions.get(self._key(scope, artifact_id), ()))
