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


def project_embeddings_2d(vectors: Sequence[Sequence[float]]) -> list[tuple[float, float]]:
    """Project a small related embedding set onto two deterministic local axes."""
    if not vectors:
        return []
    width = len(vectors[0])
    if not width or any(len(vector) != width for vector in vectors):
        return []
    center = [sum(float(vector[column]) for vector in vectors) / len(vectors)
              for column in range(width)]
    centered = [[float(value) - center[column] for column, value in enumerate(vector)]
                for vector in vectors]

    def norm(vector: Sequence[float]) -> float:
        return math.sqrt(sum(value * value for value in vector))

    first = max(centered, key=norm)
    first_norm = norm(first)
    axis_x = [value / first_norm for value in first] if first_norm else [0.0] * width
    residuals = []
    for vector in centered:
        projection = sum(value * axis for value, axis in zip(vector, axis_x))
        residuals.append([value - projection * axis for value, axis in zip(vector, axis_x)])
    second = max(residuals, key=norm)
    second_norm = norm(second)
    axis_y = [value / second_norm for value in second] if second_norm else [0.0] * width
    raw = [(
        sum(value * axis for value, axis in zip(vector, axis_x)),
        sum(value * axis for value, axis in zip(vector, axis_y)),
    ) for vector in centered]
    scale_x = max((abs(x) for x, _ in raw), default=1.0) or 1.0
    scale_y = max((abs(y) for _, y in raw), default=1.0) or 1.0
    return [(round(x / scale_x, 5), round(y / scale_y, 5)) for x, y in raw]


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
