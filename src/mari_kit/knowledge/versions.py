"""Grouping and representative proposals for immutable manifestations."""

from __future__ import annotations

import math
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
from typing import Generic, TypeVar

ItemT = TypeVar("ItemT")


@dataclass(frozen=True, slots=True, kw_only=True)
class VersionFamily(Generic[ItemT]):
    family_id: Hashable
    members: tuple[ItemT, ...]
    representative: ItemT
    tied_representatives: tuple[ItemT, ...]
    scores: tuple[tuple[ItemT, float], ...]


def resolve_version_families(
    items: Iterable[ItemT],
    *,
    family: Callable[[ItemT], Hashable],
    score: Callable[[ItemT], float],
) -> tuple[VersionFamily[ItemT], ...]:
    """Group manifestations and propose a representative with tie visibility."""

    grouped: dict[Hashable, list[ItemT]] = {}
    for item in items:
        grouped.setdefault(family(item), []).append(item)
    result: list[VersionFamily[ItemT]] = []
    for family_id, members in sorted(grouped.items(), key=lambda row: repr(row[0])):
        scored = tuple(
            sorted(
                ((item, float(score(item))) for item in members),
                key=lambda row: (-row[1], repr(row[0])),
            )
        )
        if any(not math.isfinite(value) for _, value in scored):
            raise ValueError("version representative scores must be finite")
        best = scored[0][1]
        tied = tuple(item for item, value in scored if value == best)
        result.append(
            VersionFamily(
                family_id=family_id,
                members=tuple(sorted(members, key=repr)),
                representative=tied[0],
                tied_representatives=tied,
                scores=scored,
            )
        )
    return tuple(result)
