"""Fine-grained dependency and change-impact decisions for governed knowledge."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from mari_components.types import Evidence


class FreshnessStatus(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    MISSING = "missing"
    UNVERSIONED = "unversioned"


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeDependency:
    """The exact document or document section required by a derived artifact."""

    document_id: str
    revision: str
    section_id: str = ""
    section_revision: str = ""

    def __post_init__(self) -> None:
        if not self.document_id or not self.revision:
            raise ValueError("dependency document ID and revision are required")
        if bool(self.section_id) != bool(self.section_revision):
            raise ValueError(
                "dependency section ID and section revision must be supplied together"
            )

    @property
    def dependency_id(self) -> str:
        return (
            f"{self.document_id}#{self.section_id}"
            if self.section_id
            else self.document_id
        )


@dataclass(frozen=True, slots=True)
class RevisionChange:
    document_id: str
    expected_revision: str
    current_revision: str
    section_id: str = ""

    @property
    def dependency_id(self) -> str:
        return (
            f"{self.document_id}#{self.section_id}"
            if self.section_id
            else self.document_id
        )


@dataclass(frozen=True, slots=True)
class FreshnessReport:
    status: FreshnessStatus
    changes: tuple[RevisionChange, ...] = ()
    missing_dependency_ids: tuple[str, ...] = ()
    unversioned_dependency_ids: tuple[str, ...] = ()

    @property
    def reusable(self) -> bool:
        return self.status is FreshnessStatus.CURRENT


def evidence_dependencies(
    evidence: Iterable[Evidence],
) -> tuple[KnowledgeDependency, ...]:
    """Return unambiguous document or section dependencies from exact evidence."""
    dependencies: dict[tuple[str, str], KnowledgeDependency] = {}
    for item in evidence:
        dependency = KnowledgeDependency(
            document_id=item.document_id,
            revision=item.revision,
            section_id=item.section_id,
            section_revision=item.section_revision,
        )
        key = (dependency.document_id, dependency.section_id)
        previous = dependencies.get(key)
        if previous is not None and previous != dependency:
            raise ValueError(
                f"evidence references multiple revisions of {dependency.dependency_id!r}",
            )
        dependencies[key] = dependency
    return tuple(dependencies[key] for key in sorted(dependencies))


def assess_dependencies(
    dependencies: Iterable[KnowledgeDependency],
    current_revisions: Mapping[str, str],
    *,
    current_section_revisions: Mapping[tuple[str, str], str] | None = None,
) -> FreshnessReport:
    """Assess arbitrary derived-artifact dependencies against current knowledge.

    Section dependencies use section revisions when a current section map is
    supplied. This intentionally ignores unrelated changes to the containing
    document. Without a section map, the document revision remains the safe
    fallback.
    """
    missing: list[str] = []
    unversioned: list[str] = []
    changes: list[RevisionChange] = []
    for dependency in dependencies:
        if dependency.document_id not in current_revisions:
            missing.append(dependency.document_id)
            continue
        if dependency.section_id and current_section_revisions is not None:
            key = (dependency.document_id, dependency.section_id)
            if key not in current_section_revisions:
                missing.append(dependency.dependency_id)
                continue
            expected = dependency.section_revision
            current = current_section_revisions[key]
            section_id = dependency.section_id
        else:
            expected = dependency.revision
            current = current_revisions[dependency.document_id]
            section_id = ""
        if not expected or not current:
            unversioned.append(dependency.dependency_id)
        elif expected != current:
            changes.append(
                RevisionChange(
                    dependency.document_id,
                    expected,
                    current,
                    section_id,
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
    return FreshnessReport(
        status,
        tuple(sorted(changes, key=lambda row: row.dependency_id)),
        tuple(sorted(set(missing))),
        tuple(sorted(set(unversioned))),
    )


def assess_freshness(
    evidence: Iterable[Evidence],
    current_revisions: Mapping[str, str],
    *,
    current_section_revisions: Mapping[tuple[str, str], str] | None = None,
) -> FreshnessReport:
    """Decide whether an evidence-backed artifact is safe to reuse."""
    return assess_dependencies(
        evidence_dependencies(evidence),
        current_revisions,
        current_section_revisions=current_section_revisions,
    )


def impacted_artifacts(
    artifacts: Mapping[str, Iterable[KnowledgeDependency]],
    current_revisions: Mapping[str, str],
    *,
    current_section_revisions: Mapping[tuple[str, str], str] | None = None,
) -> Mapping[str, FreshnessReport]:
    """Return every stale or missing derived artifact with its exact reason."""
    impacts: dict[str, FreshnessReport] = {}
    for artifact_id, dependencies in artifacts.items():
        report = assess_dependencies(
            dependencies,
            current_revisions,
            current_section_revisions=current_section_revisions,
        )
        if not report.reusable:
            impacts[artifact_id] = report
    return MappingProxyType(dict(sorted(impacts.items())))
