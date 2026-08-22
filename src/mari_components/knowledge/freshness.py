"""Revision dependency and staleness decisions for governed knowledge."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from mari_components.types import Evidence


class FreshnessStatus(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    MISSING = "missing"
    UNVERSIONED = "unversioned"


@dataclass(frozen=True, slots=True)
class RevisionChange:
    document_id: str
    expected_revision: str
    current_revision: str


@dataclass(frozen=True, slots=True)
class FreshnessReport:
    status: FreshnessStatus
    changes: tuple[RevisionChange, ...] = ()
    missing_document_ids: tuple[str, ...] = ()
    unversioned_document_ids: tuple[str, ...] = ()

    @property
    def reusable(self) -> bool:
        return self.status is FreshnessStatus.CURRENT


def evidence_dependencies(evidence: Iterable[Evidence]) -> Mapping[str, str]:
    """Return the exact document revisions required by an artifact.

    Conflicting revisions for one document are rejected because such an
    artifact cannot have one unambiguous freshness decision.
    """
    dependencies: dict[str, str] = {}
    for item in evidence:
        previous = dependencies.get(item.document_id)
        if previous is not None and previous != item.revision:
            raise ValueError(
                f"evidence references multiple revisions of {item.document_id!r}",
            )
        dependencies[item.document_id] = item.revision
    return dependencies


def assess_freshness(
    evidence: Iterable[Evidence],
    current_revisions: Mapping[str, str],
) -> FreshnessReport:
    """Decide whether an evidence-backed artifact is safe to reuse."""
    dependencies = evidence_dependencies(evidence)
    missing = tuple(sorted(key for key in dependencies if key not in current_revisions))
    unversioned = tuple(
        sorted(
            key
            for key, revision in dependencies.items()
            if not revision or not current_revisions.get(key, "")
        )
    )
    changes = tuple(
        sorted(
            (
                RevisionChange(key, revision, current_revisions[key])
                for key, revision in dependencies.items()
                if key in current_revisions
                and revision
                and current_revisions[key]
                and revision != current_revisions[key]
            ),
            key=lambda change: change.document_id,
        )
    )
    if missing:
        status = FreshnessStatus.MISSING
    elif unversioned:
        status = FreshnessStatus.UNVERSIONED
    elif changes:
        status = FreshnessStatus.STALE
    else:
        status = FreshnessStatus.CURRENT
    return FreshnessReport(status, changes, missing, unversioned)
