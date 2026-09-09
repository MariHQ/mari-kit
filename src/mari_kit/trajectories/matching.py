"""Reference-trajectory comparison without framework message types."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from .normalize import TrajectoryStep


class TrajectoryMatchMode(StrEnum):
    STRICT = "strict"
    UNORDERED = "unordered"
    SUBSEQUENCE = "subsequence"
    SUPERSEQUENCE = "supersequence"


StepMatches = Callable[[TrajectoryStep, TrajectoryStep], bool]


@dataclass(frozen=True, slots=True, kw_only=True)
class TrajectoryMatch:
    mode: TrajectoryMatchMode
    matched: bool
    aligned_pairs: tuple[tuple[int, int], ...]
    missing_reference_indices: tuple[int, ...]
    unexpected_observed_indices: tuple[int, ...]
    edit_distance: int
    normalized_similarity: float


def _default_match(left: TrajectoryStep, right: TrajectoryStep) -> bool:
    return left.tool == right.tool and dict(left.arguments) == dict(right.arguments)


def trajectory_edit_distance(
    observed: Sequence[TrajectoryStep],
    reference: Sequence[TrajectoryStep],
    *,
    matches: StepMatches = _default_match,
) -> int:
    """Return Levenshtein distance under a caller-replaceable step matcher."""

    previous = list(range(len(reference) + 1))
    for left_index, left in enumerate(observed, 1):
        current = [left_index]
        for right_index, right in enumerate(reference, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + int(not matches(left, right)),
                )
            )
        previous = current
    return previous[-1]


def compare_trajectories(
    observed: Sequence[TrajectoryStep],
    reference: Sequence[TrajectoryStep],
    *,
    mode: TrajectoryMatchMode = TrajectoryMatchMode.STRICT,
    matches: StepMatches = _default_match,
) -> TrajectoryMatch:
    """Compare two paths and retain their alignment and unmatched positions."""

    left, right = tuple(observed), tuple(reference)
    if mode is TrajectoryMatchMode.STRICT:
        pairs = tuple(
            (index, index)
            for index in range(min(len(left), len(right)))
            if matches(left[index], right[index])
        )
        success = len(left) == len(right) and len(pairs) == len(left)
    elif mode is TrajectoryMatchMode.UNORDERED:
        available = list(range(len(right)))
        found: list[tuple[int, int]] = []
        for left_index, step in enumerate(left):
            hit = next(
                (index for index in available if matches(step, right[index])), None
            )
            if hit is not None:
                found.append((left_index, hit))
                available.remove(hit)
        pairs = tuple(found)
        success = len(left) == len(right) == len(pairs)
    else:
        needle, haystack = (
            (left, right) if mode is TrajectoryMatchMode.SUBSEQUENCE else (right, left)
        )
        found = []
        offset = 0
        for needle_index, step in enumerate(needle):
            hit = next(
                (
                    index
                    for index in range(offset, len(haystack))
                    if matches(step, haystack[index])
                ),
                None,
            )
            if hit is None:
                break
            found.append(
                (needle_index, hit)
                if mode is TrajectoryMatchMode.SUBSEQUENCE
                else (hit, needle_index)
            )
            offset = hit + 1
        pairs = tuple(found)
        success = len(pairs) == len(needle)

    observed_matched = {left_index for left_index, _ in pairs}
    reference_matched = {right_index for _, right_index in pairs}
    distance = trajectory_edit_distance(left, right, matches=matches)
    scale = max(len(left), len(right), 1)
    return TrajectoryMatch(
        mode=mode,
        matched=success,
        aligned_pairs=pairs,
        missing_reference_indices=tuple(
            index for index in range(len(right)) if index not in reference_matched
        ),
        unexpected_observed_indices=tuple(
            index for index in range(len(left)) if index not in observed_matched
        ),
        edit_distance=distance,
        normalized_similarity=max(0.0, 1.0 - distance / scale),
    )


def tool_histogram(steps: Sequence[TrajectoryStep]) -> Counter[str]:
    """Count tools without discarding repeated calls."""

    return Counter(step.tool for step in steps)
