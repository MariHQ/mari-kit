"""Task-adaptive rubric values and confidence-visible trajectory scoring."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from mari_components.errors import MalformedModelOutput
from mari_components.json import require_list

from .process import TrajectoryRun

TRAJECTORY_RUBRIC_VERSION = "trajectory-rubric-v1"


@dataclass(frozen=True, slots=True, kw_only=True)
class RubricDimension:
    dimension_id: str
    description: str
    weight: float = 1.0
    required: bool = False

    def __post_init__(self) -> None:
        if not self.dimension_id.strip() or not self.description.strip():
            raise ValueError("rubric dimension identity and description are required")
        if not 0 < self.weight:
            raise ValueError("rubric dimension weight must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class TrajectoryRubric:
    task: str
    dimensions: tuple[RubricDimension, ...]
    schema_version: str = TRAJECTORY_RUBRIC_VERSION

    def __post_init__(self) -> None:
        ids = [item.dimension_id for item in self.dimensions]
        if not self.task.strip() or not ids or len(ids) != len(set(ids)):
            raise ValueError("rubric task and unique dimensions are required")
        object.__setattr__(self, "dimensions", tuple(self.dimensions))


@dataclass(frozen=True, slots=True, kw_only=True)
class RubricAssessment:
    trajectory_id: str
    dimension_id: str
    score: float
    confidence: float
    evidence_steps: tuple[int, ...]
    explanation: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class RubricScore:
    trajectory_id: str
    overall: float
    dimension_scores: Mapping[str, float]
    dimension_confidence: Mapping[str, float]
    missing_dimensions: tuple[str, ...]
    required_failures: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "dimension_scores", MappingProxyType(dict(self.dimension_scores))
        )
        object.__setattr__(
            self,
            "dimension_confidence",
            MappingProxyType(dict(self.dimension_confidence)),
        )


def parse_trajectory_rubric(task: str, model_output: object) -> TrajectoryRubric:
    """Validate a caller-model's task-specific rubric proposal."""

    rows = require_list(model_output, "dimensions", recipe=TRAJECTORY_RUBRIC_VERSION)
    dimensions: list[RubricDimension] = []
    for row in rows:
        try:
            weight = float(row.get("weight", 1.0))
        except (TypeError, ValueError) as error:
            raise MalformedModelOutput(
                "rubric dimension weight must be numeric"
            ) from error
        try:
            dimensions.append(
                RubricDimension(
                    dimension_id=str(row.get("id") or "")[:80],
                    description=str(row.get("description") or "")[:500],
                    weight=weight,
                    required=bool(row.get("required", False)),
                )
            )
        except ValueError as error:
            raise MalformedModelOutput(str(error)) from error
    try:
        return TrajectoryRubric(task=task, dimensions=tuple(dimensions))
    except ValueError as error:
        raise MalformedModelOutput(str(error)) from error


def parse_rubric_assessments(
    run: TrajectoryRun,
    rubric: TrajectoryRubric,
    model_output: object,
) -> tuple[RubricAssessment, ...]:
    """Validate per-dimension scores and their exact observed step evidence."""

    rows = require_list(model_output, "assessments", recipe=TRAJECTORY_RUBRIC_VERSION)
    known = {item.dimension_id for item in rubric.dimensions}
    output: list[RubricAssessment] = []
    seen: set[str] = set()
    for row in rows:
        dimension_id = str(row.get("dimension_id") or "")
        if dimension_id not in known or dimension_id in seen:
            raise MalformedModelOutput(
                "rubric assessment dimension is unknown or repeated"
            )
        try:
            score = float(row["score"])
            confidence = float(row.get("confidence", 1.0))
        except (KeyError, TypeError, ValueError) as error:
            raise MalformedModelOutput(
                "rubric score and confidence must be numeric"
            ) from error
        if not 0 <= score <= 1 or not 0 <= confidence <= 1:
            raise MalformedModelOutput("rubric score and confidence must be in [0, 1]")
        raw_steps = row.get("evidence_steps", [])
        if not isinstance(raw_steps, list) or any(
            isinstance(index, bool) or not isinstance(index, int) for index in raw_steps
        ):
            raise MalformedModelOutput("rubric evidence steps must be integer indices")
        evidence_steps = tuple(sorted(set(raw_steps)))
        if any(index < 0 or index >= len(run.steps) for index in evidence_steps):
            raise MalformedModelOutput("rubric evidence is outside the trajectory")
        output.append(
            RubricAssessment(
                trajectory_id=run.trajectory_id,
                dimension_id=dimension_id,
                score=score,
                confidence=confidence,
                evidence_steps=evidence_steps,
                explanation=str(row.get("explanation") or "")[:1000],
            )
        )
        seen.add(dimension_id)
    return tuple(output)


def score_trajectory_rubric(
    run: TrajectoryRun,
    rubric: TrajectoryRubric,
    assessments: Iterable[RubricAssessment],
    *,
    required_minimum: float = 0.5,
) -> RubricScore:
    """Aggregate dimensions while keeping missing and required failures visible."""

    if not 0 <= required_minimum <= 1:
        raise ValueError("required minimum must be in [0, 1]")
    values = tuple(assessments)
    if any(item.trajectory_id != run.trajectory_id for item in values):
        raise ValueError("rubric assessment belongs to another trajectory")
    by_dimension: dict[str, list[RubricAssessment]] = {}
    for item in values:
        by_dimension.setdefault(item.dimension_id, []).append(item)
    known = {item.dimension_id for item in rubric.dimensions}
    if set(by_dimension) - known:
        raise ValueError("rubric assessment uses an unknown dimension")
    scores: dict[str, float] = {}
    confidence: dict[str, float] = {}
    for dimension_id, rows in by_dimension.items():
        total_confidence = sum(row.confidence for row in rows)
        scores[dimension_id] = (
            sum(row.score * row.confidence for row in rows) / total_confidence
            if total_confidence
            else sum(row.score for row in rows) / len(rows)
        )
        confidence[dimension_id] = total_confidence / len(rows)
    missing = tuple(
        item.dimension_id
        for item in rubric.dimensions
        if item.dimension_id not in scores
    )
    scored_dimensions = [
        item for item in rubric.dimensions if item.dimension_id in scores
    ]
    total_weight = sum(item.weight for item in scored_dimensions)
    overall = (
        sum(scores[item.dimension_id] * item.weight for item in scored_dimensions)
        / total_weight
        if total_weight
        else 0.0
    )
    required_failures = tuple(
        item.dimension_id
        for item in rubric.dimensions
        if item.required
        and (
            item.dimension_id not in scores
            or scores[item.dimension_id] < required_minimum
        )
    )
    return RubricScore(
        trajectory_id=run.trajectory_id,
        overall=overall,
        dimension_scores=scores,
        dimension_confidence=confidence,
        missing_dimensions=missing,
        required_failures=required_failures,
    )
