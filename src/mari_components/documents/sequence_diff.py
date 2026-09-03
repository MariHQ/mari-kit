"""Myers and patience sequence alignment with coalesced edit spans."""

from __future__ import annotations

from collections import Counter
from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar

ValueT = TypeVar("ValueT", bound=Hashable)


class DiffKind(StrEnum):
    EQUAL = "equal"
    INSERT = "insert"
    DELETE = "delete"
    REPLACE = "replace"


@dataclass(frozen=True, slots=True, kw_only=True)
class DiffSpan:
    kind: DiffKind
    old_start: int
    old_end: int
    new_start: int
    new_end: int


def myers_diff(old: Sequence[ValueT], new: Sequence[ValueT]) -> tuple[DiffSpan, ...]:
    """Return a shortest insert/delete edit script, coalesced into spans."""

    n, m = len(old), len(new)
    if not n and not m:
        return ()
    frontier: dict[int, int] = {1: 0}
    trace: list[dict[int, int]] = []
    for distance in range(n + m + 1):
        trace.append(frontier.copy())
        for diagonal in range(-distance, distance + 1, 2):
            if diagonal == -distance or (
                diagonal != distance
                and frontier.get(diagonal - 1, -1) < frontier.get(diagonal + 1, -1)
            ):
                x = frontier.get(diagonal + 1, 0)
            else:
                x = frontier.get(diagonal - 1, 0) + 1
            y = x - diagonal
            while x < n and y < m and old[x] == new[y]:
                x += 1
                y += 1
            frontier[diagonal] = x
            if x >= n and y >= m:
                return _coalesce(_backtrack(trace, old, new, distance))
    raise AssertionError("Myers search did not terminate")


def patience_diff(old: Sequence[ValueT], new: Sequence[ValueT]) -> tuple[DiffSpan, ...]:
    """Anchor unique common values, using Myers within unmatched regions."""

    spans = _patience_region(old, new, 0, len(old), 0, len(new))
    return _coalesce_spans(spans)


def _patience_region(
    old: Sequence[ValueT],
    new: Sequence[ValueT],
    old_start: int,
    old_end: int,
    new_start: int,
    new_end: int,
) -> list[DiffSpan]:
    old_values = old[old_start:old_end]
    new_values = new[new_start:new_end]
    old_counts = Counter(old_values)
    new_counts = Counter(new_values)
    new_positions = {
        value: new_start + index
        for index, value in enumerate(new_values)
        if new_counts[value] == 1
    }
    pairs = [
        (old_start + index, new_positions[value])
        for index, value in enumerate(old_values)
        if old_counts[value] == 1 and value in new_positions
    ]
    anchors = _longest_increasing_pairs(pairs)
    if not anchors:
        return [
            DiffSpan(
                kind=span.kind,
                old_start=span.old_start + old_start,
                old_end=span.old_end + old_start,
                new_start=span.new_start + new_start,
                new_end=span.new_end + new_start,
            )
            for span in myers_diff(old_values, new_values)
        ]
    output: list[DiffSpan] = []
    left_old, left_new = old_start, new_start
    for anchor_old, anchor_new in anchors:
        output.extend(
            _patience_region(old, new, left_old, anchor_old, left_new, anchor_new)
        )
        output.append(
            DiffSpan(
                kind=DiffKind.EQUAL,
                old_start=anchor_old,
                old_end=anchor_old + 1,
                new_start=anchor_new,
                new_end=anchor_new + 1,
            )
        )
        left_old, left_new = anchor_old + 1, anchor_new + 1
    output.extend(_patience_region(old, new, left_old, old_end, left_new, new_end))
    return output


def _longest_increasing_pairs(
    pairs: Sequence[tuple[int, int]],
) -> tuple[tuple[int, int], ...]:
    if not pairs:
        return ()
    tails: list[int] = []
    tail_indices: list[int] = []
    previous = [-1] * len(pairs)
    for index, (_, position) in enumerate(pairs):
        low, high = 0, len(tails)
        while low < high:
            middle = (low + high) // 2
            if tails[middle] < position:
                low = middle + 1
            else:
                high = middle
        if low == len(tails):
            tails.append(position)
            tail_indices.append(index)
        else:
            tails[low] = position
            tail_indices[low] = index
        if low:
            previous[index] = tail_indices[low - 1]
    chain: list[tuple[int, int]] = []
    cursor = tail_indices[-1]
    while cursor >= 0:
        chain.append(pairs[cursor])
        cursor = previous[cursor]
    return tuple(reversed(chain))


def _backtrack(
    trace: Sequence[dict[int, int]],
    old: Sequence[ValueT],
    new: Sequence[ValueT],
    distance: int,
) -> list[tuple[DiffKind, int, int]]:
    x, y = len(old), len(new)
    output: list[tuple[DiffKind, int, int]] = []
    for depth in range(distance, 0, -1):
        frontier = trace[depth]
        diagonal = x - y
        if diagonal == -depth or (
            diagonal != depth
            and frontier.get(diagonal - 1, -1) < frontier.get(diagonal + 1, -1)
        ):
            previous_diagonal = diagonal + 1
            operation = DiffKind.INSERT
        else:
            previous_diagonal = diagonal - 1
            operation = DiffKind.DELETE
        previous_x = frontier.get(previous_diagonal, 0)
        previous_y = previous_x - previous_diagonal
        while x > previous_x and y > previous_y:
            output.append((DiffKind.EQUAL, x - 1, y - 1))
            x -= 1
            y -= 1
        if operation is DiffKind.DELETE:
            output.append((operation, x - 1, y))
            x -= 1
        else:
            output.append((operation, x, y - 1))
            y -= 1
    while x > 0 and y > 0:
        output.append((DiffKind.EQUAL, x - 1, y - 1))
        x -= 1
        y -= 1
    while x > 0:
        output.append((DiffKind.DELETE, x - 1, y))
        x -= 1
    while y > 0:
        output.append((DiffKind.INSERT, x, y - 1))
        y -= 1
    return list(reversed(output))


def _coalesce(operations: Sequence[tuple[DiffKind, int, int]]) -> tuple[DiffSpan, ...]:
    spans: list[DiffSpan] = []
    old_cursor = new_cursor = 0
    for kind, _, _ in operations:
        old_size = int(kind in {DiffKind.EQUAL, DiffKind.DELETE})
        new_size = int(kind in {DiffKind.EQUAL, DiffKind.INSERT})
        span = DiffSpan(
            kind=kind,
            old_start=old_cursor,
            old_end=old_cursor + old_size,
            new_start=new_cursor,
            new_end=new_cursor + new_size,
        )
        old_cursor += old_size
        new_cursor += new_size
        if spans and spans[-1].kind is kind:
            previous = spans[-1]
            spans[-1] = DiffSpan(
                kind=kind,
                old_start=previous.old_start,
                old_end=span.old_end,
                new_start=previous.new_start,
                new_end=span.new_end,
            )
        else:
            spans.append(span)
    return _merge_replacements(spans)


def _coalesce_spans(spans: Sequence[DiffSpan]) -> tuple[DiffSpan, ...]:
    output: list[DiffSpan] = []
    for span in spans:
        if (
            output
            and output[-1].kind is span.kind
            and output[-1].old_end == span.old_start
            and output[-1].new_end == span.new_start
        ):
            previous = output[-1]
            output[-1] = DiffSpan(
                kind=span.kind,
                old_start=previous.old_start,
                old_end=span.old_end,
                new_start=previous.new_start,
                new_end=span.new_end,
            )
        else:
            output.append(span)
    return _merge_replacements(output)


def _merge_replacements(spans: Sequence[DiffSpan]) -> tuple[DiffSpan, ...]:
    output: list[DiffSpan] = []
    index = 0
    while index < len(spans):
        current = spans[index]
        if index + 1 < len(spans) and {
            current.kind,
            spans[index + 1].kind,
        } == {DiffKind.DELETE, DiffKind.INSERT}:
            following = spans[index + 1]
            output.append(
                DiffSpan(
                    kind=DiffKind.REPLACE,
                    old_start=min(current.old_start, following.old_start),
                    old_end=max(current.old_end, following.old_end),
                    new_start=min(current.new_start, following.new_start),
                    new_end=max(current.new_end, following.new_end),
                )
            )
            index += 2
        else:
            output.append(current)
            index += 1
    return tuple(output)
