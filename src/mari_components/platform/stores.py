"""Reference in-memory store for revision and point-in-time conformance."""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Any

from mari_components.knowledge.artifacts import KnowledgeArtifact, KnowledgeScope


class RevisionConflict(RuntimeError):
    """The caller's expected current revision did not match storage."""


class InMemoryArtifactStore:
    """Minimal reference semantics; production adapters run against the same cases."""

    def __init__(self) -> None:
        self._revisions: dict[tuple[str, str], list[KnowledgeArtifact[Any]]] = (
            defaultdict(list)
        )

    def commit(
        self,
        artifact: KnowledgeArtifact[Any],
        *,
        expected_revision: str | None,
    ) -> None:
        key = (artifact.scope.tenant, artifact.artifact_id)
        revisions = self._revisions[key]
        current = revisions[-1].revision if revisions else None
        if current != expected_revision:
            raise RevisionConflict(f"expected {expected_revision!r}, found {current!r}")
        if any(value.revision == artifact.revision for value in revisions):
            raise ValueError("artifact revision already exists")
        if revisions and f"{artifact.artifact_id}@{current}" not in artifact.supersedes:
            raise ValueError(
                "a new revision must explicitly supersede the current revision"
            )
        revisions.append(artifact)

    def get(
        self, artifact_id: str, *, scope: KnowledgeScope
    ) -> KnowledgeArtifact[Any] | None:
        revisions = self._revisions.get((scope.tenant, artifact_id), ())
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
        revisions = self._revisions.get((scope.tenant, artifact_id), ())
        visible = [value for value in revisions if value.recorded_at <= known_at]
        return visible[-1] if visible else None

    def history(
        self, artifact_id: str, *, scope: KnowledgeScope
    ) -> tuple[KnowledgeArtifact[Any], ...]:
        return tuple(self._revisions.get((scope.tenant, artifact_id), ()))
