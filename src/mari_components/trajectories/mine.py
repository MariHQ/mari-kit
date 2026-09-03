"""Grounded trajectory analysis using one caller-supplied model invocation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from mari_components.errors import MalformedModelOutput
from mari_components.json import require_object

from .normalize import DEFAULT_FAMILY_MAP, TrajectoryStep, normalize_steps

TRAJECTORY_VERSION = "trajectory-mining-v2"


@dataclass(frozen=True, slots=True, kw_only=True)
class TrajectoryPhase:
    name: str
    family: str
    start: int
    end: int
    substate: str
    failures: int

    @property
    def steps(self) -> int:
        return self.end - self.start + 1


@dataclass(frozen=True, slots=True, kw_only=True)
class TrajectoryAnalysis:
    grounded_workflow: str
    activity: str
    category: str
    macro_intent: str
    steps: tuple[TrajectoryStep, ...]
    phases: tuple[TrajectoryPhase, ...]
    rework: int
    schema_version: str = TRAJECTORY_VERSION


def _required(value: Mapping[str, object], key: str) -> str:
    result = str(value.get(key) or "").strip()
    if not result:
        raise MalformedModelOutput(f"trajectory {key} is required")
    return result


def parse_trajectory_analysis(
    events: Iterable[Mapping[str, object]],
    model_output: object,
    *,
    family_map: Mapping[str, str] = DEFAULT_FAMILY_MAP,
) -> TrajectoryAnalysis:
    """Validate a model's labels against the exact observable event sequence."""
    steps = normalize_steps(events, family_map=family_map)
    value = require_object(model_output, recipe=TRAJECTORY_VERSION)
    raw_phases = value.get("phases")
    if not isinstance(raw_phases, list):
        raise MalformedModelOutput("trajectory phases must be a list")
    phases: list[TrajectoryPhase] = []
    expected_start = 0
    for raw in raw_phases:
        if not isinstance(raw, dict):
            raise MalformedModelOutput("each trajectory phase must be an object")
        try:
            start, end = int(raw["start"]), int(raw["end"])
        except (KeyError, TypeError, ValueError) as error:
            raise MalformedModelOutput(
                "trajectory phase bounds must be integers"
            ) from error
        if start != expected_start or end < start or end >= len(steps):
            raise MalformedModelOutput(
                "trajectory phases must cover steps contiguously"
            )
        name = str(raw.get("name") or "").strip()
        family = str(raw.get("family") or "").strip()
        substate = str(raw.get("substate") or "").strip()
        if not name or not family or not substate:
            raise MalformedModelOutput("trajectory phase labels are required")
        phases.append(
            TrajectoryPhase(
                name=name[:120],
                family=family[:60],
                start=start,
                end=end,
                substate=substate[:60],
                failures=sum(step.ok is False for step in steps[start : end + 1]),
            )
        )
        expected_start = end + 1
    if steps and expected_start != len(steps):
        raise MalformedModelOutput("trajectory phases must cover every step")
    if not steps and phases:
        raise MalformedModelOutput("an empty trajectory cannot have phases")
    try:
        rework = int(value.get("rework", 0))
    except (TypeError, ValueError) as error:
        raise MalformedModelOutput(
            "trajectory rework must be a non-negative integer"
        ) from error
    if rework < 0:
        raise MalformedModelOutput("trajectory rework must be a non-negative integer")
    return TrajectoryAnalysis(
        grounded_workflow=_required(value, "workflow")[:3000],
        activity=_required(value, "activity")[:600],
        category=_required(value, "category")[:100],
        macro_intent=_required(value, "intent")[:120],
        steps=steps,
        phases=tuple(phases),
        rework=rework,
    )
