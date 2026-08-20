"""Progressive, grounded trajectory abstraction using an injected JSON model."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Iterable, Mapping, Sequence

from mari_components.errors import MalformedModelOutput
from mari_components.json import JsonGenerator, require_object
from .normalize import DEFAULT_FAMILY_MAP, TrajectoryStep, normalize_steps
from .segment import TrajectoryPhase, rework_count, segment_phases


TRAJECTORY_VERSION = "trajectory-mining-v1"


@dataclass(frozen=True, slots=True)
class TrajectoryAnalysis:
    grounded_workflow: str
    activity: str
    category: str
    macro_intent: str
    steps: tuple[TrajectoryStep, ...]
    phases: tuple[TrajectoryPhase, ...]
    rework: int
    prompt_version: str = TRAJECTORY_VERSION


def _text(steps: Iterable[TrajectoryStep]) -> str:
    return "\n".join(
        f"{step.ordinal + 1}. {step.tool} [{step.action_family}] {'ok' if step.ok else 'failed'}: "
        f"{step.summary} args={json.dumps(dict(step.arguments), sort_keys=True)}"
        for step in steps
    )


def _required(value: object, key: str, label: str) -> str:
    result = str(require_object(value, recipe=TRAJECTORY_VERSION).get(key) or "").strip()
    if not result:
        raise MalformedModelOutput(f"trajectory {label} is required")
    return result


def analyze_trajectory(
    user_prompt: str,
    events: Iterable[Mapping[str, object]],
    *,
    generate_json: JsonGenerator,
    taxonomy: Sequence[str] = (),
    family_map: Mapping[str, str] = DEFAULT_FAMILY_MAP,
) -> TrajectoryAnalysis:
    steps = normalize_steps(events, family_map=family_map)
    phases = segment_phases(steps)
    telemetry = _text(steps)
    grounded = _required(
        generate_json(
            "Describe this workflow using only the chronological tool telemetry. Mention observable failures and recovery. "
            'Return JSON {"workflow":"2-5 grounded sentences"}.\n' + telemetry,
            TRAJECTORY_VERSION,
        ),
        "workflow",
        "workflow",
    )
    activity = _required(
        generate_json(
            'Compress the grounded workflow into one activity without adding facts. Return JSON {"activity":"one sentence"}.\n' + grounded,
            TRAJECTORY_VERSION,
        ),
        "activity",
        "activity",
    )
    category = _required(
        generate_json(
            "Assign the activity to a stable workflow taxonomy. Prefer an existing category when it fits. "
            f'Existing: {json.dumps(list(taxonomy))}. Return JSON {{"category":"..."}}.\n{activity}',
            TRAJECTORY_VERSION,
        ),
        "category",
        "category",
    )
    macro = _required(
        generate_json(
            'Name the user macro intent in at most six words. Return JSON {"intent":"..."}.\n' + user_prompt[:1200],
            TRAJECTORY_VERSION,
        ),
        "intent",
        "macro intent",
    )
    return TrajectoryAnalysis(grounded[:3000], activity[:600], category[:100], macro[:120], steps, phases, rework_count(steps))
