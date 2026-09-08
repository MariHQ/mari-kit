"""Topology-only link-candidate scoring."""

from __future__ import annotations

import math
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
from typing import Literal, TypeVar

NodeT = TypeVar("NodeT", bound=Hashable)


@dataclass(frozen=True, slots=True, kw_only=True)
class LinkScore:
    left: Hashable
    right: Hashable
    method: str
    score: float
    common_neighbors: tuple[Hashable, ...]


def score_link_candidates(
    *,
    candidate_pairs: Iterable[tuple[NodeT, NodeT]],
    neighbors: Callable[[NodeT], Iterable[NodeT]],
    method: Literal["common_neighbors", "jaccard", "adamic_adar"] = "jaccard",
) -> tuple[LinkScore, ...]:
    results: list[LinkScore] = []
    for left, right in candidate_pairs:
        left_neighbors = set(neighbors(left))
        right_neighbors = set(neighbors(right))
        common = left_neighbors & right_neighbors
        if method == "common_neighbors":
            score = float(len(common))
        elif method == "jaccard":
            union = left_neighbors | right_neighbors
            score = len(common) / len(union) if union else 0.0
        elif method == "adamic_adar":
            score = sum(
                1.0 / math.log(len(set(neighbors(node))))
                for node in common
                if len(set(neighbors(node))) > 1
            )
        else:
            raise ValueError(f"unsupported link score: {method}")
        results.append(
            LinkScore(
                left=left,
                right=right,
                method=method,
                score=score,
                common_neighbors=tuple(sorted(common, key=repr)),
            )
        )
    return tuple(
        sorted(
            results, key=lambda item: (-item.score, repr(item.left), repr(item.right))
        )
    )


def simrank_scores(
    nodes: Iterable[NodeT],
    *,
    incoming: Callable[[NodeT], Iterable[NodeT]],
    decay: float = 0.8,
    iterations: int = 10,
) -> tuple[tuple[NodeT, NodeT, float], ...]:
    """Compute deterministic all-pairs SimRank over a bounded node set."""

    values = tuple(sorted(set(nodes), key=repr))
    if not 0 <= decay <= 1 or iterations < 1:
        raise ValueError("decay must be in [0, 1] and iterations positive")
    known = set(values)
    parents = {
        node: tuple(item for item in set(incoming(node)) if item in known)
        for node in values
    }
    scores = {
        (left, right): float(left == right) for left in values for right in values
    }
    for _ in range(iterations):
        updated = dict(scores)
        for index, left in enumerate(values):
            for right in values[index + 1 :]:
                left_parents, right_parents = parents[left], parents[right]
                value = 0.0
                if left_parents and right_parents:
                    value = (
                        decay
                        * sum(
                            scores[(a, b)] for a in left_parents for b in right_parents
                        )
                        / (len(left_parents) * len(right_parents))
                    )
                updated[(left, right)] = updated[(right, left)] = value
        scores = updated
    return tuple(
        (left, right, scores[(left, right)])
        for index, left in enumerate(values)
        for right in values[index + 1 :]
    )
