"""Caller-embedded intent clustering, novelty detection, and temporal drift."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from .intents import IntentCandidate


@dataclass(frozen=True, slots=True, kw_only=True)
class IntentCluster:
    cluster_id: str
    medoid_id: str
    candidate_ids: tuple[str, ...]
    labels: tuple[str, ...]
    cohesion: float
    ambiguous_candidate_ids: tuple[str, ...] = ()

    @property
    def support(self) -> int:
        return len(self.candidate_ids)


@dataclass(frozen=True, slots=True, kw_only=True)
class IntentClustering:
    clusters: tuple[IntentCluster, ...]
    threshold: float


@dataclass(frozen=True, slots=True, kw_only=True)
class NovelIntent:
    candidate_id: str
    nearest_cluster_id: str
    similarity: float
    novel: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class IntentClusterChange:
    before_cluster_id: str
    after_cluster_id: str
    before_mass: float
    after_mass: float
    mass_delta: float


@dataclass(frozen=True, slots=True, kw_only=True)
class IntentDriftReport:
    divergence: float
    changes: tuple[IntentClusterChange, ...]
    new_cluster_ids: tuple[str, ...]
    retired_cluster_ids: tuple[str, ...]
    before_total: int
    after_total: int


def cluster_intents(
    candidates: Iterable[IntentCandidate],
    embeddings: Mapping[str, Sequence[float]],
    *,
    similarity_threshold: float = 0.82,
    ambiguity_margin: float = 0.03,
) -> IntentClustering:
    """Single-link candidate intents using caller-owned embeddings."""

    if not -1 <= similarity_threshold <= 1 or ambiguity_margin < 0:
        raise ValueError("invalid similarity threshold or ambiguity margin")
    values = tuple(candidates)
    ids = [item.candidate_id for item in values]
    if len(ids) != len(set(ids)):
        raise ValueError("intent candidate IDs must be unique")
    matrix = _matrix(ids, embeddings)
    parent = list(range(len(values)))

    def root(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        a, b = root(left), root(right)
        if a != b:
            parent[max(a, b)] = min(a, b)

    similarities = matrix @ matrix.T if len(values) else np.empty((0, 0))
    for left in range(len(values)):
        for right in range(left + 1, len(values)):
            if similarities[left, right] >= similarity_threshold:
                union(left, right)
    components: dict[int, list[int]] = {}
    for index in range(len(values)):
        components.setdefault(root(index), []).append(index)
    provisional: list[tuple[list[int], int, float]] = []
    for members in components.values():
        medoid = min(
            members,
            key=lambda index: (
                -float(np.mean(similarities[index, members])),
                ids[index],
            ),
        )
        cohesion = float(np.mean(similarities[np.ix_(members, members)]))
        provisional.append((members, medoid, cohesion))
    medoids = [medoid for _, medoid, _ in provisional]
    clusters: list[IntentCluster] = []
    for members, medoid, cohesion in provisional:
        ambiguous: list[str] = []
        for index in members:
            own = float(similarities[index, medoid])
            alternatives = [
                float(similarities[index, other])
                for other in medoids
                if other != medoid
            ]
            if alternatives and own - max(alternatives) <= ambiguity_margin:
                ambiguous.append(ids[index])
        member_ids = tuple(sorted(ids[index] for index in members))
        clusters.append(
            IntentCluster(
                cluster_id=f"intent-cluster:{ids[medoid]}",
                medoid_id=ids[medoid],
                candidate_ids=member_ids,
                labels=tuple(sorted({values[index].intent for index in members})),
                cohesion=cohesion,
                ambiguous_candidate_ids=tuple(sorted(ambiguous)),
            )
        )
    return IntentClustering(
        clusters=tuple(sorted(clusters, key=lambda item: item.cluster_id)),
        threshold=similarity_threshold,
    )


def detect_novel_intents(
    candidates: Iterable[IntentCandidate],
    embeddings: Mapping[str, Sequence[float]],
    known_centroids: Mapping[str, Sequence[float]],
    *,
    threshold: float = 0.75,
) -> tuple[NovelIntent, ...]:
    """Report distance from known caller clusters without assigning a taxonomy."""

    if not -1 <= threshold <= 1 or not known_centroids:
        raise ValueError("threshold must be in [-1, 1] and centroids are required")
    values = tuple(candidates)
    ids = [item.candidate_id for item in values]
    candidate_matrix = _matrix(ids, embeddings)
    centroid_ids = sorted(known_centroids)
    centroid_matrix = _matrix(centroid_ids, known_centroids)
    output: list[NovelIntent] = []
    for index, candidate_id in enumerate(ids):
        scores = candidate_matrix[index] @ centroid_matrix.T
        nearest = min(
            range(len(centroid_ids)),
            key=lambda item: (-float(scores[item]), centroid_ids[item]),
        )
        similarity = float(scores[nearest])
        output.append(
            NovelIntent(
                candidate_id=candidate_id,
                nearest_cluster_id=centroid_ids[nearest],
                similarity=similarity,
                novel=similarity < threshold,
            )
        )
    return tuple(output)


def compare_intent_windows(
    before: IntentClustering,
    after: IntentClustering,
    *,
    cluster_matches: Mapping[str, str] | None = None,
) -> IntentDriftReport:
    """Compare caller-matched intent clusters using Jensen-Shannon divergence."""

    left = {item.cluster_id: item for item in before.clusters}
    right = {item.cluster_id: item for item in after.clusters}
    matches = dict(cluster_matches or {})
    if not matches:
        matches = {key: key for key in left.keys() & right.keys()}
    if set(matches) - left.keys() or set(matches.values()) - right.keys():
        raise ValueError("cluster matches reference unknown clusters")
    if len(set(matches.values())) != len(matches):
        raise ValueError("after clusters may be matched at most once")
    left_total = sum(item.support for item in left.values())
    right_total = sum(item.support for item in right.values())
    changes = tuple(
        IntentClusterChange(
            before_cluster_id=left_id,
            after_cluster_id=right_id,
            before_mass=left[left_id].support / left_total if left_total else 0.0,
            after_mass=right[right_id].support / right_total if right_total else 0.0,
            mass_delta=(right[right_id].support / right_total if right_total else 0.0)
            - (left[left_id].support / left_total if left_total else 0.0),
        )
        for left_id, right_id in sorted(matches.items())
    )
    retired = tuple(sorted(left.keys() - matches.keys()))
    matched_right = set(matches.values())
    new = tuple(sorted(right.keys() - matched_right))
    before_distribution = (
        [item.before_mass for item in changes]
        + [left[key].support / left_total for key in retired]
        + [0.0 for _ in new]
    )
    after_distribution = (
        [item.after_mass for item in changes]
        + [0.0 for _ in retired]
        + [right[key].support / right_total for key in new]
    )
    return IntentDriftReport(
        divergence=_jensen_shannon(before_distribution, after_distribution),
        changes=changes,
        new_cluster_ids=new,
        retired_cluster_ids=retired,
        before_total=left_total,
        after_total=right_total,
    )


def _matrix(ids: Sequence[str], vectors: Mapping[str, Sequence[float]]) -> np.ndarray:
    if set(ids) - vectors.keys():
        raise ValueError("an embedding is required for every identifier")
    rows = [np.asarray(vectors[key], dtype=np.float64) for key in ids]
    if not rows:
        return np.empty((0, 0))
    if (
        any(row.ndim != 1 or not row.size for row in rows)
        or len({row.shape for row in rows}) != 1
    ):
        raise ValueError("embeddings must be non-empty one-dimensional peers")
    matrix = np.stack(rows)
    if not np.all(np.isfinite(matrix)):
        raise ValueError("embeddings must be finite")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError("embeddings must have non-zero norm")
    return matrix / norms


def _jensen_shannon(left: Sequence[float], right: Sequence[float]) -> float:
    middle = [(a + b) / 2 for a, b in zip(left, right, strict=True)]

    def divergence(values: Sequence[float]) -> float:
        return sum(
            value * math.log2(value / center)
            for value, center in zip(values, middle, strict=True)
            if value > 0 and center > 0
        )

    return (divergence(left) + divergence(right)) / 2
