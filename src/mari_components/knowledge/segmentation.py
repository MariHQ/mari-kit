"""Topic-aware segmentation for bounded memory consolidation."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

ItemT = TypeVar("ItemT")


@dataclass(frozen=True, slots=True, kw_only=True)
class TopicSegment(Generic[ItemT]):
    start: int
    stop: int
    items: tuple[ItemT, ...]


def hybrid_topic_segments(
    items: Sequence[ItemT],
    attention_boundaries: Sequence[float],
    adjacent_similarities: Sequence[float],
    *,
    similarity_threshold: float,
) -> tuple[TopicSegment[ItemT], ...]:
    """Split at boundaries that are both attention peaks and similarity valleys.

    Boundary signal ``i`` lies between ``items[i]`` and ``items[i + 1]``. As in
    LightMem, only interior local maxima in the attention boundary sequence are
    eligible; semantic similarity must also be below ``similarity_threshold``.
    """
    values = tuple(items)
    if not values:
        return ()
    expected = len(values) - 1
    if len(attention_boundaries) != expected or len(adjacent_similarities) != expected:
        raise ValueError("boundary signals must have len(items) - 1 values")
    if not math.isfinite(similarity_threshold):
        raise ValueError("similarity_threshold must be finite")

    attention = tuple(float(value) for value in attention_boundaries)
    similarities = tuple(float(value) for value in adjacent_similarities)
    if any(not math.isfinite(value) for value in attention + similarities):
        raise ValueError("boundary signals must be finite")

    boundaries = [
        index + 1
        for index in range(1, expected - 1)
        if attention[index] > attention[index - 1]
        and attention[index] > attention[index + 1]
        and similarities[index] < similarity_threshold
    ]
    stops = boundaries + [len(values)]
    starts = [0] + boundaries
    return tuple(
        TopicSegment(start=start, stop=stop, items=values[start:stop])
        for start, stop in zip(starts, stops, strict=True)
    )
