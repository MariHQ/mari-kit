"""Deterministic coarse-to-fine trajectory phase segmentation."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from typing import Iterable

from .normalize import TrajectoryStep


@dataclass(frozen=True, slots=True)
class TrajectoryPhase:
    identifier: int
    name: str
    family: str
    start: int
    end: int
    steps: int
    substate: str
    failures: int


def segment_phases(steps: Iterable[TrajectoryStep]) -> tuple[TrajectoryPhase, ...]:
    values = tuple(steps)
    if not values:
        return ()
    phases: list[TrajectoryPhase] = []
    start = 0
    for index in range(1, len(values) + 1):
        boundary = index == len(values)
        if not boundary:
            before, after = values[index - 1], values[index]
            boundary = before.action_family != after.action_family or (not before.ok and after.ok)
        if not boundary:
            continue
        chunk = values[start:index]
        family = Counter(step.action_family for step in chunk).most_common(1)[0][0]
        failures = sum(not step.ok for step in chunk)
        substate = "Recovery" if failures and chunk[-1].ok else ("Blocked" if failures else "Progress")
        phases.append(TrajectoryPhase(len(phases), family.capitalize(), family, start, index - 1, len(chunk), substate, failures))
        start = index
    return tuple(phases)


def rework_count(steps: Iterable[TrajectoryStep]) -> int:
    values = tuple(steps)
    signatures = Counter((step.tool, json.dumps(dict(step.arguments), sort_keys=True)) for step in values)
    repeated = sum(max(0, count - 1) for count in signatures.values())
    families = [step.action_family for step in values]
    loops = sum(families[index:index + 3] == ["change", "inspect", "change"] for index in range(max(0, len(families) - 2)))
    return repeated + loops
