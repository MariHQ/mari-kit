"""Diversity-aware sampling for inspecting large trajectory corpora."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True, kw_only=True)
class TrajectorySample:
    trajectory_id: str
    rank: int
    score: float
    relevance: float
    density: float
    minimum_distance: float


@dataclass(frozen=True, slots=True, kw_only=True)
class TrajectorySamplingResult:
    selected: tuple[TrajectorySample, ...]
    excluded_ids: tuple[str, ...]


def select_diverse_trajectories(
    vectors: Mapping[str, Sequence[float]],
    *,
    limit: int,
    relevance: Mapping[str, float] | None = None,
    density: Mapping[str, float] | None = None,
    distance_exponent: float = 1.0,
) -> TrajectorySamplingResult:
    """Greedily balance importance and distance from already selected traces.

    Vectors are normalized and compared in their original space. ``relevance``
    and ``density`` are caller-provided non-negative weights; Mari does not
    prescribe an embedding model, density estimator, or intent taxonomy.
    """

    if limit < 0 or distance_exponent <= 0:
        raise ValueError("limit must be non-negative and distance exponent positive")
    ids = tuple(sorted(vectors))
    if not ids or limit == 0:
        return TrajectorySamplingResult(selected=(), excluded_ids=ids)
    rows = [np.asarray(vectors[key], dtype=np.float64) for key in ids]
    dimensions = {row.shape for row in rows}
    if len(dimensions) != 1 or rows[0].ndim != 1 or rows[0].size == 0:
        raise ValueError("trajectory vectors must be non-empty one-dimensional peers")
    matrix = np.stack(rows)
    if not np.all(np.isfinite(matrix)):
        raise ValueError("trajectory vectors must be finite")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    matrix = np.divide(matrix, norms, out=np.zeros_like(matrix), where=norms != 0)
    rel = np.asarray([_weight(relevance, key) for key in ids])
    den = np.asarray([_weight(density, key) for key in ids])
    importance = rel * den
    selected_indices: list[int] = []
    minimum_distances = np.full(len(ids), 2.0)
    selected: list[TrajectorySample] = []
    for rank in range(min(limit, len(ids))):
        scores = (
            importance
            if rank == 0
            else importance * minimum_distances**distance_exponent
        )
        available = [
            index for index in range(len(ids)) if index not in selected_indices
        ]
        chosen = min(available, key=lambda index: (-float(scores[index]), ids[index]))
        chosen_distance = 0.0 if rank == 0 else float(minimum_distances[chosen])
        selected.append(
            TrajectorySample(
                trajectory_id=ids[chosen],
                rank=rank,
                score=float(scores[chosen]),
                relevance=float(rel[chosen]),
                density=float(den[chosen]),
                minimum_distance=chosen_distance,
            )
        )
        selected_indices.append(chosen)
        distances = 1.0 - matrix @ matrix[chosen]
        minimum_distances = np.minimum(minimum_distances, np.clip(distances, 0.0, 2.0))
    chosen_ids = {item.trajectory_id for item in selected}
    return TrajectorySamplingResult(
        selected=tuple(selected),
        excluded_ids=tuple(key for key in ids if key not in chosen_ids),
    )


def _weight(values: Mapping[str, float] | None, key: str) -> float:
    if values is None:
        return 1.0
    value = float(values.get(key, 1.0))
    if not np.isfinite(value) or value < 0:
        raise ValueError("trajectory weights must be finite and non-negative")
    return value
