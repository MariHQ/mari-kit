"""Evidence-bound turn, episode, and cross-episode reflection values."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from mari_components.errors import MalformedModelOutput
from mari_components.json import require_list, require_object

from .process import TrajectoryRun

EPISODE_VERSION = "trajectory-episode-v1"


class AssessmentStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True, kw_only=True)
class TurnAssessment:
    turn_id: str
    trajectory_id: str
    start: int
    end: int
    situation: str
    intent: str
    action: str
    assessment: AssessmentStatus
    goal_progress: str = ""
    evidence_steps: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class Episode:
    episode_id: str
    trajectory_id: str
    turn_ids: tuple[str, ...]
    start: int
    end: int
    situation: str
    intent: str
    outcome: AssessmentStatus
    justification: str
    insights: tuple[str, ...] = ()
    pitfalls: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class EpisodeReflection:
    reflection_id: str
    focal_episode_id: str
    comparison_episode_ids: tuple[str, ...]
    applicability: tuple[str, ...]
    hints: tuple[str, ...]
    pitfalls: tuple[str, ...]
    confidence: float


def parse_turn_assessments(
    run: TrajectoryRun, model_output: object
) -> tuple[TurnAssessment, ...]:
    """Validate turn summaries against inclusive step ranges in one trajectory."""

    rows = require_list(model_output, "turns", recipe=EPISODE_VERSION)
    output: list[TurnAssessment] = []
    occupied: set[int] = set()
    for index, row in enumerate(rows):
        start, end = _bounds(row, len(run.steps), "turn")
        evidence = _indices(
            row.get("evidence_steps", list(range(start, end + 1))), len(run.steps)
        )
        situation = str(row.get("situation") or "").strip()[:700]
        intent = str(row.get("intent") or "").strip()[:500]
        action = str(row.get("action") or "").strip()[:700]
        if not situation or not intent or not action:
            raise MalformedModelOutput(
                "turn situation, intent, and action are required"
            )
        if occupied & set(range(start, end + 1)):
            raise MalformedModelOutput("turn ranges must not overlap")
        occupied.update(range(start, end + 1))
        try:
            assessment = AssessmentStatus(str(row.get("assessment") or "unknown"))
        except ValueError as error:
            raise MalformedModelOutput("turn assessment is invalid") from error
        identity = f"{run.trajectory_id}\0{start}\0{end}\0{index}"
        output.append(
            TurnAssessment(
                turn_id=f"turn:{hashlib.sha256(identity.encode()).hexdigest()[:20]}",
                trajectory_id=run.trajectory_id,
                start=start,
                end=end,
                situation=situation,
                intent=intent,
                action=action,
                assessment=assessment,
                goal_progress=str(row.get("goal_progress") or "")[:700],
                evidence_steps=evidence,
            )
        )
    return tuple(sorted(output, key=lambda item: (item.start, item.end)))


def segment_episodes(
    run: TrajectoryRun,
    turns: Iterable[TurnAssessment],
    *,
    boundaries: Iterable[int],
) -> tuple[Episode, ...]:
    """Group ordered turns at caller-supplied inclusive boundary indices."""

    values = tuple(sorted(turns, key=lambda item: (item.start, item.end)))
    if any(item.trajectory_id != run.trajectory_id for item in values):
        raise ValueError("turn belongs to another trajectory")
    supplied_ends = tuple(boundaries)
    ends = tuple(sorted(set(supplied_ends)))
    if supplied_ends != ends:
        raise ValueError("episode boundaries must be strictly increasing")
    if values and (not ends or ends[-1] != len(values) - 1):
        raise ValueError("episode boundaries must include the final turn")
    if any(index < 0 or index >= len(values) for index in ends):
        raise ValueError("episode boundary is outside the turn sequence")
    output: list[Episode] = []
    first = 0
    for last in ends:
        group = values[first : last + 1]
        if not group:
            raise ValueError("episode boundaries must be strictly increasing")
        statuses = {item.assessment for item in group}
        outcome = (
            AssessmentStatus.FAILURE
            if AssessmentStatus.FAILURE in statuses
            else AssessmentStatus.PARTIAL
            if AssessmentStatus.PARTIAL in statuses
            else AssessmentStatus.SUCCESS
            if statuses == {AssessmentStatus.SUCCESS}
            else AssessmentStatus.UNKNOWN
        )
        identity = f"{run.trajectory_id}\0{group[0].start}\0{group[-1].end}"
        output.append(
            Episode(
                episode_id=f"episode:{hashlib.sha256(identity.encode()).hexdigest()[:20]}",
                trajectory_id=run.trajectory_id,
                turn_ids=tuple(item.turn_id for item in group),
                start=group[0].start,
                end=group[-1].end,
                situation=group[0].situation,
                intent=group[-1].intent,
                outcome=outcome,
                justification="; ".join(
                    item.goal_progress for item in group if item.goal_progress
                )[:1_500],
            )
        )
        first = last + 1
    return tuple(output)


def parse_episode_reflection(
    focal: Episode,
    comparisons: Iterable[Episode],
    model_output: object,
) -> EpisodeReflection:
    """Validate a proposed cross-episode insight without promoting it to memory."""

    peers = {item.episode_id: item for item in comparisons}
    value = require_object(model_output, recipe=EPISODE_VERSION)
    raw_ids = value.get("comparison_episode_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        raise MalformedModelOutput("reflection comparison episodes are required")
    ids = tuple(dict.fromkeys(str(item) for item in raw_ids))
    if set(ids) - peers.keys() or focal.episode_id in ids:
        raise MalformedModelOutput("reflection references an unknown or focal episode")
    try:
        confidence = float(value.get("confidence", 0.0))
    except (TypeError, ValueError) as error:
        raise MalformedModelOutput("reflection confidence must be numeric") from error
    if not 0 <= confidence <= 1:
        raise MalformedModelOutput("reflection confidence must be in [0, 1]")
    applicability = _strings(value.get("applicability"), "applicability", required=True)
    hints = _strings(value.get("hints"), "hints", required=True)
    pitfalls = _strings(value.get("pitfalls"), "pitfalls", required=False)
    identity = "\0".join((focal.episode_id, *ids, *applicability, *hints, *pitfalls))
    return EpisodeReflection(
        reflection_id=f"reflection:{hashlib.sha256(identity.encode()).hexdigest()[:20]}",
        focal_episode_id=focal.episode_id,
        comparison_episode_ids=ids,
        applicability=applicability,
        hints=hints,
        pitfalls=pitfalls,
        confidence=confidence,
    )


def _bounds(row: Mapping[str, object], length: int, label: str) -> tuple[int, int]:
    if isinstance(row.get("start"), bool) or isinstance(row.get("end"), bool):
        raise MalformedModelOutput(f"{label} bounds must be integers")
    raw_start, raw_end = row.get("start"), row.get("end")
    if not isinstance(raw_start, (str, int, float)) or not isinstance(
        raw_end, (str, int, float)
    ):
        raise MalformedModelOutput(f"{label} bounds must be integers")
    try:
        start, end = int(raw_start), int(raw_end)
    except (TypeError, ValueError) as error:
        raise MalformedModelOutput(f"{label} bounds must be integers") from error
    if start < 0 or end < start or end >= length:
        raise MalformedModelOutput(f"{label} range is outside the trajectory")
    return start, end


def _indices(value: object, length: int) -> tuple[int, ...]:
    if not isinstance(value, list) or any(
        isinstance(item, bool) or not isinstance(item, int) for item in value
    ):
        raise MalformedModelOutput("turn evidence steps must be integer indices")
    result = tuple(sorted(set(value)))
    if any(item < 0 or item >= length for item in result):
        raise MalformedModelOutput("turn evidence is outside the trajectory")
    return result


def _strings(value: object, name: str, *, required: bool) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise MalformedModelOutput(f"reflection {name} must be strings")
    result = tuple(item.strip()[:500] for item in value if item.strip())
    if required and not result:
        raise MalformedModelOutput(f"reflection {name} is required")
    return result
