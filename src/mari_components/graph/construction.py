"""Deterministic blocking and threshold clustering for caller-owned entities."""

from __future__ import annotations

import math
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
from typing import TypeVar

NodeT = TypeVar("NodeT", bound=Hashable)


def candidate_pairs(
    *,
    entity_ids: Iterable[NodeT],
    blocking_keys: Callable[[NodeT], Iterable[Hashable]],
) -> tuple[tuple[NodeT, NodeT], ...]:
    """Return stable unique pairs sharing at least one caller-defined key."""

    blocks: dict[Hashable, set[NodeT]] = {}
    for entity_id in set(entity_ids):
        for key in set(blocking_keys(entity_id)):
            blocks.setdefault(key, set()).add(entity_id)
    pairs: set[tuple[NodeT, NodeT]] = set()
    for values in blocks.values():
        ordered = sorted(values, key=repr)
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                pairs.add((left, right))
    return tuple(sorted(pairs, key=lambda pair: (repr(pair[0]), repr(pair[1]))))


@dataclass(frozen=True, slots=True, kw_only=True)
class MatchLink:
    left: Hashable
    right: Hashable
    score: float


@dataclass(frozen=True, slots=True, kw_only=True)
class ClusterResult:
    clusters: tuple[tuple[Hashable, ...], ...]
    assignments: tuple[tuple[Hashable, int], ...]
    accepted_links: tuple[MatchLink, ...]
    rejected_links: tuple[MatchLink, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceBoundCandidate:
    candidate: object
    evidence: tuple[object, ...]
    accepted: bool
    reason: str


def bind_relation_evidence(
    candidates: Iterable[object],
    *,
    resolve: Callable[[object], Iterable[object]],
) -> tuple[EvidenceBoundCandidate, ...]:
    """Resolve evidence without asserting or persisting relation candidates."""

    result: list[EvidenceBoundCandidate] = []
    for candidate in candidates:
        evidence = tuple(resolve(candidate))
        result.append(
            EvidenceBoundCandidate(
                candidate=candidate,
                evidence=evidence,
                accepted=bool(evidence),
                reason="evidence_resolved" if evidence else "missing_evidence",
            )
        )
    return tuple(result)


def cluster_matches(
    *,
    entity_ids: Iterable[NodeT],
    candidate_pairs: Iterable[tuple[NodeT, NodeT]],
    score: Callable[[NodeT, NodeT], float],
    threshold: float,
) -> ClusterResult:
    if not math.isfinite(threshold):
        raise ValueError("threshold must be finite")
    entities = set(entity_ids)
    parent = {entity: entity for entity in entities}

    def find(item: NodeT) -> NodeT:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: NodeT, right: NodeT) -> None:
        a, b = find(left), find(right)
        if a != b:
            first, second = sorted((a, b), key=repr)
            parent[second] = first

    accepted: list[MatchLink] = []
    rejected: list[MatchLink] = []
    for left, right in sorted(set(candidate_pairs), key=lambda pair: (repr(pair[0]), repr(pair[1]))):
        if left not in entities or right not in entities:
            raise ValueError("candidate pairs must reference supplied entity IDs")
        value = float(score(left, right))
        if not math.isfinite(value):
            raise ValueError("pair scores must be finite")
        link = MatchLink(left=left, right=right, score=value)
        if value >= threshold:
            accepted.append(link)
            union(left, right)
        else:
            rejected.append(link)
    grouped: dict[NodeT, list[NodeT]] = {}
    for entity in entities:
        grouped.setdefault(find(entity), []).append(entity)
    clusters = tuple(sorted((tuple(sorted(group, key=repr)) for group in grouped.values()), key=lambda group: (-len(group), repr(group))))
    assignments = tuple((entity, index) for index, group in enumerate(clusters) for entity in group)
    return ClusterResult(clusters=clusters, assignments=assignments, accepted_links=tuple(accepted), rejected_links=tuple(rejected))
