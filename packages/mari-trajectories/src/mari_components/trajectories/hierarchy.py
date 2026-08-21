"""Embedding-driven matching over WorkflowView's workflow/phase/step hierarchy."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class HierarchyMatch:
    workflow_id: int
    workflow_score: float
    phase_index: int
    phase_score: float
    step_index: int
    step_score: float


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    denominator = math.sqrt(sum(v * v for v in left)) * math.sqrt(sum(v * v for v in right))
    return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0


def match_hierarchy(
    query_embedding: Sequence[float], workflows: Iterable[Mapping], *, minimum_score: float,
) -> HierarchyMatch | None:
    """Choose the closest workflow, then its closest phase and atomic step."""
    ranked = [(cosine(query_embedding, row.get("embedding") or ()), row) for row in workflows]
    score, workflow = max(ranked, key=lambda item: item[0], default=(0.0, None))
    if workflow is None or score < minimum_score:
        return None
    phases = list(workflow.get("phases") or ())
    phase_score, phase_index = max(
        ((cosine(query_embedding, phase.get("embedding") or ()), index)
         for index, phase in enumerate(phases)), default=(0.0, 0),
    )
    steps = list(workflow.get("steps") or ())
    phase_steps = [(index, step) for index, step in enumerate(steps)
                   if int(step.get("phase_index") or 0) == phase_index]
    step_score, step_index = max(
        ((cosine(query_embedding, step.get("embedding") or ()), index)
         for index, step in phase_steps), default=(0.0, phase_steps[0][0] if phase_steps else 0),
    )
    return HierarchyMatch(
        int(workflow["id"]), score, phase_index, phase_score, step_index, step_score,
    )
