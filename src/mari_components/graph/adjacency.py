"""Adjacency projections over caller-owned edge iterables."""

from __future__ import annotations

from collections.abc import Callable, Hashable, Iterable, Mapping
from types import MappingProxyType
from typing import TypeVar

NodeT = TypeVar("NodeT", bound=Hashable)
EdgeT = TypeVar("EdgeT")


def build_adjacency(
    edges: Iterable[EdgeT],
    *,
    endpoints: Callable[[EdgeT], tuple[NodeT, NodeT]],
    direction: str = "outgoing",
    include: Callable[[EdgeT], bool] = lambda _edge: True,
    nodes: Iterable[NodeT] = (),
) -> Mapping[NodeT, tuple[NodeT, ...]]:
    """Project edges into deterministic adjacency without retaining a graph."""

    if direction not in {"outgoing", "incoming", "both"}:
        raise ValueError("direction must be outgoing, incoming, or both")
    values: dict[NodeT, set[NodeT]] = {node: set() for node in nodes}
    for edge in edges:
        if not include(edge):
            continue
        left, right = endpoints(edge)
        values.setdefault(left, set())
        values.setdefault(right, set())
        if direction in {"outgoing", "both"}:
            values[left].add(right)
        if direction in {"incoming", "both"}:
            values[right].add(left)
    return MappingProxyType(
        {
            node: tuple(sorted(neighbors, key=repr))
            for node, neighbors in sorted(
                values.items(), key=lambda item: repr(item[0])
            )
        }
    )
