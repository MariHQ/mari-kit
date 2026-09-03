"""Half-open interval operations independent of graph representation."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
from typing import Generic, TypeVar

ValueT = TypeVar("ValueT")
LeftT = TypeVar("LeftT")
RightT = TypeVar("RightT")


@dataclass(frozen=True, slots=True, kw_only=True)
class TimeInterval:
    start: dt.datetime | None = None
    end: dt.datetime | None = None

    def __post_init__(self) -> None:
        if self.start is not None and self.end is not None and self.end <= self.start:
            raise ValueError("interval end must be later than start")


def interval_intersection(left: TimeInterval, right: TimeInterval) -> TimeInterval | None:
    starts = [value for value in (left.start, right.start) if value is not None]
    ends = [value for value in (left.end, right.end) if value is not None]
    start = max(starts) if starts else None
    end = min(ends) if ends else None
    if start is not None and end is not None and end <= start:
        return None
    return TimeInterval(start=start, end=end)


@dataclass(frozen=True, slots=True, kw_only=True)
class TemporalJoinPair(Generic[LeftT, RightT]):
    left: LeftT
    right: RightT
    overlap: TimeInterval


def temporal_join(
    left: Iterable[LeftT],
    right: Iterable[RightT],
    *,
    left_key: Callable[[LeftT], Hashable],
    right_key: Callable[[RightT], Hashable],
    left_interval: Callable[[LeftT], TimeInterval],
    right_interval: Callable[[RightT], TimeInterval],
) -> tuple[TemporalJoinPair[LeftT, RightT], ...]:
    right_by_key: dict[Hashable, list[RightT]] = {}
    for item in right:
        right_by_key.setdefault(right_key(item), []).append(item)
    result: list[TemporalJoinPair[LeftT, RightT]] = []
    for left_item in left:
        for right_item in right_by_key.get(left_key(left_item), ()):
            overlap = interval_intersection(left_interval(left_item), right_interval(right_item))
            if overlap is not None:
                result.append(TemporalJoinPair(left=left_item, right=right_item, overlap=overlap))
    return tuple(result)
