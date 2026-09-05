"""Dedupe-inspired blocking, active acquisition, clustering and matching choices."""

from __future__ import annotations

import importlib
import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class BlockingPredicate:
    name: str
    covered_pairs: frozenset[str]
    comparison_cost: float

    def __post_init__(self) -> None:
        if (
            not self.name
            or not math.isfinite(self.comparison_cost)
            or self.comparison_cost < 0
        ):
            raise ValueError("name and finite nonnegative comparison cost required")


@dataclass(frozen=True)
class BlockingSelection:
    predicates: tuple[str, ...]
    covered: frozenset[str]
    target: int
    cost: float
    optimal: bool
    feasible: bool
    explored: int


def learn_blocking(
    predicates: Sequence[BlockingPredicate],
    matches: frozenset[str],
    *,
    recall: float = 1,
    max_states: int = 2500,
) -> BlockingSelection:
    """Bounded branch-and-bound set cover minimizing SUM of predicate costs.

    Target is floor(recall * labeled matches), following Dedupe. Costs may count
    overlapping comparisons repeatedly. Caller generates predicates/coverage;
    this learns a disjunction, not classifiers or compound predicate generation.
    ``optimal`` certifies exhaustive search; infeasibility is explicit.
    """
    if (
        not 0 <= recall <= 1
        or max_states < 1
        or len({p.name for p in predicates}) != len(predicates)
    ):
        raise ValueError("invalid recall, state budget or duplicate names")
    target = int(recall * len(matches))
    covers = [p.covered_pairs & matches for p in predicates]
    suffix: list[frozenset[str]] = [frozenset() for _ in range(len(predicates) + 1)]
    for i in range(len(predicates) - 1, -1, -1):
        suffix[i] = suffix[i + 1] | covers[i]
    stack: list[tuple[int, tuple[int, ...], frozenset[str], float]] = [
        (0, (), frozenset(), 0.0)
    ]
    best: tuple[int, ...] = ()
    best_cover: frozenset[str] = frozenset()
    best_cost = math.inf
    explored = 0
    while stack and explored < max_states:
        i, chosen, covered, cost = stack.pop()
        explored += 1
        if cost >= best_cost:
            continue
        if len(covered) >= target:
            best, best_cover, best_cost = chosen, covered, cost
            continue
        if i == len(predicates) or len(covered | suffix[i]) < target:
            continue
        stack.append((i + 1, chosen, covered, cost))
        stack.append(
            (
                i + 1,
                (*chosen, i),
                covered | covers[i],
                cost + predicates[i].comparison_cost,
            )
        )
    return BlockingSelection(
        tuple(predicates[i].name for i in best),
        best_cover,
        target,
        best_cost,
        not stack,
        math.isfinite(best_cost),
        explored,
    )


def acquire_disagreement(
    matcher: Mapping[str, float], blocked: Mapping[str, bool], *, seed: int = 0
) -> str:
    """Dedupe's matcher/blocker disagreement policy; seeded zero-weight fallback.

    First sample uncovered matcher positives proportional to probability. Else
    choose covered pair nearest a uniform random target probability. If none are
    covered, sample proportional to the two-model population standard deviation.
    """
    if (
        not matcher
        or matcher.keys() != blocked.keys()
        or any(not 0 <= p <= 1 for p in matcher.values())
        or any(not isinstance(v, bool) for v in blocked.values())
    ):
        raise ValueError(
            "matching nonempty keys, probabilities and boolean blocking required"
        )
    rng = random.Random(seed)
    candidates = [
        key
        for key, probability in matcher.items()
        if probability > 0.5 and not blocked[key]
    ]
    if candidates:
        return rng.choices(candidates, weights=[matcher[k] for k in candidates], k=1)[0]
    covered = [key for key in matcher if blocked[key]]
    if covered:
        target = rng.random()
        return min(covered, key=lambda key: abs(matcher[key] - target))
    candidates = list(matcher)
    weights = [abs(matcher[key] - blocked[key]) / 2 for key in candidates]
    return (
        rng.choices(candidates, weights=weights, k=1)[0]
        if sum(weights)
        else rng.choice(candidates)
    )


@dataclass(frozen=True)
class PairScore:
    left: str
    right: str
    score: float

    def __post_init__(self) -> None:
        if not self.left or not self.right or not 0 <= self.score <= 1:
            raise ValueError("pair IDs and probability score required")


@dataclass(frozen=True)
class LinkageCluster:
    members: tuple[str, ...]
    confidence: tuple[float, ...]


def greedy_matching(
    pairs: Sequence[PairScore], *, threshold: float = 0
) -> tuple[PairScore, ...]:
    """Descending-score greedy one-to-one bipartite matching; stable input ties."""
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be in [0,1]")
    left: set[str] = set()
    right: set[str] = set()
    result = []
    for pair in sorted(pairs, key=lambda pair: -pair.score):
        if pair.score > threshold and pair.left not in left and pair.right not in right:
            result.append(pair)
            left.add(pair.left)
            right.add(pair.right)
    return tuple(result)


def gazette_matching(
    pairs: Sequence[PairScore], *, threshold: float = 0, n_matches: int = 1
) -> tuple[PairScore, ...]:
    """Top matches per left record; right records reusable; zero means all."""
    if not 0 <= threshold <= 1 or n_matches < 0:
        raise ValueError("invalid threshold or match count")
    grouped: dict[str, dict[str, PairScore]] = {}
    for pair in pairs:
        values = grouped.setdefault(pair.left, {})
        if pair.score > threshold and (
            pair.right not in values or pair.score > values[pair.right].score
        ):
            values[pair.right] = pair
    return tuple(
        pair
        for group in grouped.values()
        for pair in sorted(group.values(), key=lambda pair: -pair.score)[
            : n_matches or None
        ]
    )


def centroid_clusters(
    pairs: Sequence[PairScore],
    *,
    threshold: float = 0.5,
    max_component_size: int = 30000,
) -> tuple[LinkageCluster, ...]:
    """Dedupe-style centroid linkage on 1-score, missing pair distance 1.

    Uses SciPy lazily; quadratic memory per connected component. Oversized
    components raise rather than silently rethresholding. Singles omitted;
    two-record components require score strictly greater than threshold.
    """
    if not 0 <= threshold <= 1 or max_component_size < 2:
        raise ValueError("invalid threshold or component size")
    try:
        hierarchy = importlib.import_module("scipy.cluster.hierarchy")
    except ImportError as exc:
        raise ImportError(
            "centroid_clusters requires mari-components[algorithm-solvers]"
        ) from exc
    adjacency: dict[str, set[str]] = {}
    scores: dict[tuple[str, str], float] = {}
    for pair in pairs:
        if pair.left == pair.right:
            raise ValueError("self pairs not supported")
        key = (min(pair.left, pair.right), max(pair.left, pair.right))
        scores[key] = max(scores.get(key, 0.0), pair.score)
        adjacency.setdefault(pair.left, set()).add(pair.right)
        adjacency.setdefault(pair.right, set()).add(pair.left)
    remaining = set(adjacency)
    result = []
    while remaining:
        stack = [min(remaining)]
        component: set[str] = set()
        while stack:
            node = stack.pop()
            if node not in component:
                component.add(node)
                if len(component) > max_component_size:
                    raise ValueError("component exceeds max_component_size")
                stack.extend(adjacency[node] - component)
        remaining -= component
        members = sorted(component)
        if len(members) == 2:
            score = scores[(members[0], members[1])]
            if score > threshold:
                result.append(LinkageCluster(tuple(members), (score, score)))
            continue
        distances = [
            1 - scores.get((a, b), 0.0)
            for i, a in enumerate(members)
            for b in members[i + 1 :]
        ]
        labels = hierarchy.fcluster(
            hierarchy.linkage(distances, method="centroid"),
            1 - threshold,
            criterion="distance",
        )
        groups: dict[int, list[str]] = {}
        for member, label in zip(members, labels, strict=True):
            groups.setdefault(int(label), []).append(member)
        for group in groups.values():
            if len(group) > 1:
                confidence = tuple(
                    1
                    - math.sqrt(
                        sum(
                            (1 - scores.get((min(a, b), max(a, b)), 0.0)) ** 2
                            for b in group
                            if b != a
                        )
                        / (len(group) - 1)
                    )
                    for a in group
                )
                result.append(LinkageCluster(tuple(group), confidence))
    return tuple(result)
