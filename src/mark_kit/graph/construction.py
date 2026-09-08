"""Deterministic blocking and threshold clustering for caller-owned entities."""

from __future__ import annotations

import math
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
from typing import Generic, TypeVar

NodeT = TypeVar("NodeT", bound=Hashable)


@dataclass(frozen=True, slots=True, kw_only=True)
class BlockedPair(Generic[NodeT]):
    left: NodeT
    right: NodeT
    shared_keys: tuple[Hashable, ...]


def explain_candidate_pairs(
    *,
    entity_ids: Iterable[NodeT],
    blocking_keys: Callable[[NodeT], Iterable[Hashable]],
) -> tuple[BlockedPair[NodeT], ...]:
    """Return candidate pairs with the caller keys that generated them."""

    keys_by_entity = {
        entity_id: set(blocking_keys(entity_id)) for entity_id in set(entity_ids)
    }
    entities = sorted(keys_by_entity, key=repr)
    result: list[BlockedPair[NodeT]] = []
    for index, left in enumerate(entities):
        for right in entities[index + 1 :]:
            shared = keys_by_entity[left] & keys_by_entity[right]
            if shared:
                result.append(
                    BlockedPair(
                        left=left,
                        right=right,
                        shared_keys=tuple(sorted(shared, key=repr)),
                    )
                )
    return tuple(result)


def candidate_pairs(
    *,
    entity_ids: Iterable[NodeT],
    blocking_keys: Callable[[NodeT], Iterable[Hashable]],
) -> tuple[tuple[NodeT, NodeT], ...]:
    """Return stable unique pairs sharing at least one caller-defined key."""

    return tuple(
        (pair.left, pair.right)
        for pair in explain_candidate_pairs(
            entity_ids=entity_ids, blocking_keys=blocking_keys
        )
    )


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


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceResolution:
    candidate: object
    evidence: tuple[object, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ClusterDiagnostic:
    cluster: tuple[Hashable, ...]
    weakest_accepted_score: float | None
    rejected_internal_links: tuple[MatchLink, ...]


def resolve_relation_evidence(
    candidates: Iterable[object],
    *,
    resolve: Callable[[object], Iterable[object]],
) -> tuple[EvidenceResolution, ...]:
    """Resolve evidence without turning evidence presence into acceptance."""

    return tuple(
        EvidenceResolution(candidate=candidate, evidence=tuple(resolve(candidate)))
        for candidate in candidates
    )


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
    for left, right in sorted(
        set(candidate_pairs), key=lambda pair: (repr(pair[0]), repr(pair[1]))
    ):
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
    clusters = tuple(
        sorted(
            (tuple(sorted(group, key=repr)) for group in grouped.values()),
            key=lambda group: (-len(group), repr(group)),
        )
    )
    assignments = tuple(
        (entity, index) for index, group in enumerate(clusters) for entity in group
    )
    return ClusterResult(
        clusters=clusters,
        assignments=assignments,
        accepted_links=tuple(accepted),
        rejected_links=tuple(rejected),
    )


def inspect_clusters(result: ClusterResult) -> tuple[ClusterDiagnostic, ...]:
    """Expose weak accepted links and rejected links inside transitive clusters."""

    diagnostics: list[ClusterDiagnostic] = []
    for cluster in result.clusters:
        members = set(cluster)
        accepted = tuple(
            link
            for link in result.accepted_links
            if link.left in members and link.right in members
        )
        rejected = tuple(
            link
            for link in result.rejected_links
            if link.left in members and link.right in members
        )
        diagnostics.append(
            ClusterDiagnostic(
                cluster=cluster,
                weakest_accepted_score=min(
                    (link.score for link in accepted), default=None
                ),
                rejected_internal_links=rejected,
            )
        )
    return tuple(diagnostics)
