"""Exact late-interaction MaxSim scoring."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def exact_maxsim(
    query_points: NDArray[np.floating],
    document_points: NDArray[np.floating],
    *,
    query_weights: NDArray[np.floating] | None = None,
) -> float:
    query = np.array(query_points, dtype=np.float32, copy=True)
    document = np.array(document_points, dtype=np.float32, copy=True)
    if query.ndim != 2 or document.ndim != 2 or not len(query) or not len(document):
        raise ValueError("MaxSim needs non-empty query and document matrices")
    if query.shape[1] != document.shape[1]:
        raise ValueError("query and document dimensions differ")
    if not np.all(np.isfinite(query)) or not np.all(np.isfinite(document)):
        raise ValueError("MaxSim vectors must be finite")
    query /= np.maximum(np.linalg.norm(query, axis=1, keepdims=True), 1e-12)
    document /= np.maximum(np.linalg.norm(document, axis=1, keepdims=True), 1e-12)
    maxima = (query @ document.T).max(axis=1)
    if query_weights is None:
        return float(maxima.mean())
    weights = np.asarray(query_weights, dtype=np.float32)
    if (
        weights.ndim != 1
        or len(weights) != len(query)
        or not np.all(np.isfinite(weights))
        or np.any(weights < 0)
        or not float(weights.sum()) > 0
    ):
        raise ValueError(
            "query weights must be a non-negative finite vector with positive sum"
        )
    return float(np.average(maxima, weights=weights))
