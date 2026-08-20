"""Exact late-interaction MaxSim scoring."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def exact_maxsim(
    query_points: NDArray[np.floating], document_points: NDArray[np.floating]
) -> float:
    query = np.array(query_points, dtype=np.float32, copy=True)
    document = np.array(document_points, dtype=np.float32, copy=True)
    if query.ndim != 2 or document.ndim != 2 or not len(query) or not len(document):
        raise ValueError("MaxSim needs non-empty query and document matrices")
    if query.shape[1] != document.shape[1]:
        raise ValueError("query and document dimensions differ")
    query /= np.maximum(np.linalg.norm(query, axis=1, keepdims=True), 1e-12)
    document /= np.maximum(np.linalg.norm(document, axis=1, keepdims=True), 1e-12)
    return float((query @ document.T).max(axis=1).sum())
