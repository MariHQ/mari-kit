"""Distill repeated observed trajectories into host-usable workflow hints."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import re
from typing import Iterable

from .mine import TrajectoryAnalysis


@dataclass(frozen=True, slots=True)
class DistilledWorkflow:
    """A repeated successful shape, not an executable framework object.

    Hosts decide whether to approve and bind the tool sequence to their own
    functions. No arguments or side effects are replayed from telemetry.
    """

    identifier: str
    name: str
    category: str
    activity: str
    tool_sequence: tuple[str, ...]
    occurrences: int
    success_rate: float


@dataclass(frozen=True, slots=True)
class WorkflowMatch:
    workflow: DistilledWorkflow
    score: float


def _terms(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.casefold()))


def distill_workflows(
    trajectories: Iterable[TrajectoryAnalysis], *, minimum_occurrences: int = 2,
    minimum_success_rate: float = 1.0,
) -> tuple[DistilledWorkflow, ...]:
    """Group analyzed trajectories by category and observable tool sequence.

    This is deliberately deterministic: expensive LLM abstraction has already
    happened in ``analyze_trajectory``. Distillation itself does not spend more
    model calls or retain tool arguments.
    """
    if minimum_occurrences < 1:
        raise ValueError("minimum_occurrences must be positive")
    if not 0 <= minimum_success_rate <= 1:
        raise ValueError("minimum_success_rate must be between zero and one")
    groups: dict[tuple[str, tuple[str, ...]], list[TrajectoryAnalysis]] = defaultdict(list)
    for trajectory in trajectories:
        sequence = tuple(
            step.tool for step in trajectory.steps
            if step.tool != "answer" and step.action_family != "other"
        )
        if sequence:
            groups[(trajectory.category, sequence)].append(trajectory)
    output: list[DistilledWorkflow] = []
    for (category, sequence), rows in groups.items():
        if len(rows) < minimum_occurrences:
            continue
        name = Counter(row.macro_intent for row in rows).most_common(1)[0][0]
        activity = Counter(row.activity for row in rows).most_common(1)[0][0]
        successes = sum(all(step.ok for step in row.steps) for row in rows)
        success_rate = successes / len(rows)
        if success_rate < minimum_success_rate:
            continue
        digest = hashlib.sha256(
            (category + "\0" + "\0".join(sequence)).encode()
        ).hexdigest()[:16]
        output.append(DistilledWorkflow(
            digest, name, category, activity, sequence, len(rows), success_rate,
        ))
    return tuple(sorted(output, key=lambda row: (-row.occurrences, row.identifier)))


def match_workflow(
    prompt: str, workflows: Iterable[DistilledWorkflow], *, minimum_score: float = 0.2,
) -> WorkflowMatch | None:
    """Select a likely fast path without another model invocation."""
    if not 0 <= minimum_score <= 1:
        raise ValueError("minimum_score must be between zero and one")
    wanted = _terms(prompt)
    if not wanted:
        return None
    ranked: list[WorkflowMatch] = []
    for workflow in workflows:
        known = _terms(f"{workflow.name} {workflow.activity} {workflow.category}")
        score = len(wanted & known) / len(wanted | known) if known else 0.0
        if score >= minimum_score:
            ranked.append(WorkflowMatch(workflow, score))
    return max(ranked, key=lambda item: (item.score, item.workflow.occurrences), default=None)
