"""Immutable records of how knowledge moved through one observed task."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import IntEnum, StrEnum


class KnowledgeObservationStage(IntEnum):
    RETRIEVED = 1
    SHOWN = 2
    CITED = 3
    USED = 4


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeObservation:
    observation_id: str
    activity_id: str
    artifact_id: str
    revision: str
    stage: KnowledgeObservationStage
    ordinal: int
    evidence: str = ""

    def __post_init__(self) -> None:
        if (
            not all(
                value.strip()
                for value in (
                    self.observation_id,
                    self.activity_id,
                    self.artifact_id,
                    self.revision,
                )
            )
            or self.ordinal < 0
        ):
            raise ValueError("knowledge observations require identity and an ordinal")


class ObservationIssueKind(StrEnum):
    DUPLICATE_ID = "duplicate_id"
    STAGE_REGRESSION = "stage_regression"
    MISSING_PREDECESSOR = "missing_predecessor"


@dataclass(frozen=True, slots=True, kw_only=True)
class ObservationIssue:
    kind: ObservationIssueKind
    observation_id: str
    artifact_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeObservationReport:
    observations: tuple[KnowledgeObservation, ...]
    retrieved: tuple[tuple[str, str], ...]
    shown: tuple[tuple[str, str], ...]
    cited: tuple[tuple[str, str], ...]
    used: tuple[tuple[str, str], ...]
    issues: tuple[ObservationIssue, ...]

    @property
    def valid(self) -> bool:
        return not self.issues


def inspect_knowledge_observations(
    observations: Iterable[KnowledgeObservation],
) -> KnowledgeObservationReport:
    """Validate stage ordering without inferring use from retrieval or citation."""

    values = tuple(
        sorted(observations, key=lambda item: (item.ordinal, item.observation_id))
    )
    issues: list[ObservationIssue] = []
    counts: dict[str, int] = {}
    highest: dict[tuple[str, str, str], KnowledgeObservationStage] = {}
    for item in values:
        counts[item.observation_id] = counts.get(item.observation_id, 0) + 1
        key = (item.activity_id, item.artifact_id, item.revision)
        previous = highest.get(key)
        if previous is not None and item.stage < previous:
            issues.append(
                ObservationIssue(
                    kind=ObservationIssueKind.STAGE_REGRESSION,
                    observation_id=item.observation_id,
                    artifact_id=item.artifact_id,
                )
            )
        if item.stage > KnowledgeObservationStage.RETRIEVED and previous is None:
            issues.append(
                ObservationIssue(
                    kind=ObservationIssueKind.MISSING_PREDECESSOR,
                    observation_id=item.observation_id,
                    artifact_id=item.artifact_id,
                )
            )
        highest[key] = max(item.stage, previous or item.stage)
    for observation_id, count in counts.items():
        if count > 1:
            first = next(
                item for item in values if item.observation_id == observation_id
            )
            issues.append(
                ObservationIssue(
                    kind=ObservationIssueKind.DUPLICATE_ID,
                    observation_id=observation_id,
                    artifact_id=first.artifact_id,
                )
            )

    def observed_at(stage: KnowledgeObservationStage) -> tuple[tuple[str, str], ...]:
        return tuple(
            sorted(
                {
                    (item.artifact_id, item.revision)
                    for item in values
                    if item.stage == stage
                }
            )
        )

    unique = {
        (item.kind, item.observation_id, item.artifact_id): item for item in issues
    }
    return KnowledgeObservationReport(
        observations=values,
        retrieved=observed_at(KnowledgeObservationStage.RETRIEVED),
        shown=observed_at(KnowledgeObservationStage.SHOWN),
        cited=observed_at(KnowledgeObservationStage.CITED),
        used=observed_at(KnowledgeObservationStage.USED),
        issues=tuple(
            unique[key] for key in sorted(unique, key=lambda row: tuple(map(str, row)))
        ),
    )
