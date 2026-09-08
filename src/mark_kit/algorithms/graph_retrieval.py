"""Selectable graph retrieval computations from HippoRAG 2, LightRAG,
Hindsight, Graphiti, and haiku.rag. See docs/algorithm-choices.md for adaptations.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np


@dataclass(frozen=True, slots=True)
class SeedWeight:
    node: str
    entity_weight: float
    passage_weight: float

    @property
    def weight(self) -> float:
        return self.entity_weight + self.passage_weight


def hipporag_seed_weights(
    facts: Iterable[tuple[str, str, float]],
    *,
    entity_passage_counts: Mapping[str, int],
    passage_scores: Mapping[str, float],
    passage_weight: float = 0.05,
    link_top_k: int | None = None,
    allowed_nodes: Iterable[str],
) -> tuple[SeedWeight, ...]:
    """Average incident fact scores / entity passage count, plus dense seeds.

    facts contain (subject node, object node, nonnegative fact relevance).
    Scores for allowed passages are min-max normalized; tied values become 0.
    Use disjoint entity/passage IDs to preserve both roles. This is the seed
    computation, independently composable with existing personalized_pagerank.
    """
    if (
        not math.isfinite(passage_weight)
        or passage_weight < 0
        or (link_top_k is not None and link_top_k < 0)
    ):
        raise ValueError("invalid passage weight or linking budget")
    allowed = set(allowed_nodes)
    samples: dict[str, list[float]] = {}
    for a, b, score in facts:
        if not math.isfinite(score) or score < 0:
            raise ValueError("nonnegative finite fact scores required")
        for node in (a, b):
            if node not in allowed:
                continue
            count = entity_passage_counts.get(node, 0)
            if count < 0:
                raise ValueError("passage counts must be nonnegative")
            samples.setdefault(node, []).append(score / max(1, count))
    entity = {node: sum(scores) / len(scores) for node, scores in samples.items()}
    ordered = sorted(entity, key=lambda node: (-entity[node], node))
    if link_top_k is not None:
        ordered = ordered[:link_top_k]
    entity = {node: entity[node] for node in ordered}
    dense = {
        node: float(score) for node, score in passage_scores.items() if node in allowed
    }
    if any(not math.isfinite(score) for score in dense.values()):
        raise ValueError("finite passage scores required")
    low, high = min(dense.values(), default=0.0), max(dense.values(), default=0.0)
    dense = {
        node: passage_weight * (score - low) / (high - low) if high > low else 0.0
        for node, score in dense.items()
    }
    return tuple(
        SeedWeight(node, entity.get(node, 0.0), dense.get(node, 0.0))
        for node in sorted(entity.keys() | dense.keys())
    )


@dataclass(frozen=True, slots=True)
class ChunkAllocation:
    chunks: tuple[str, ...]
    parent_counts: tuple[int, ...]
    quotas: tuple[int, ...]


def weighted_chunk_polling(
    parents: Sequence[Sequence[str]],
    *,
    maximum: int,
    minimum: int = 1,
    deduplicate: bool = False,
) -> ChunkAllocation:
    """LightRAG's linearly decreasing quotas and priority-ordered redistribution.

    maximum/minimum are endpoint parent quotas, not a global output limit.
    Total allocation is bounded by the sum of interpolated quotas.
    Duplicate occurrences count against quotas. Optional deduplication happens
    after allocation, with no hidden backfill; parent_counts count occurrences.
    """
    if minimum < 0 or maximum < minimum:
        raise ValueError("require maximum >= minimum >= 0")
    n = len(parents)
    quotas = [
        round(maximum - i / (n - 1) * (maximum - minimum)) if n > 1 else maximum
        for i in range(n)
    ]
    counts = [
        min(quota, len(parent)) for quota, parent in zip(quotas, parents, strict=True)
    ]
    chunks = [
        chunk
        for parent, count in zip(parents, counts, strict=True)
        for chunk in parent[:count]
    ]
    for _ in range(sum(quotas) - sum(counts)):
        for i, parent in enumerate(parents):
            if counts[i] < len(parent):
                chunks.append(parent[counts[i]])
                counts[i] += 1
                break
        else:
            break
    return ChunkAllocation(
        tuple(dict.fromkeys(chunks)) if deduplicate else tuple(chunks),
        tuple(counts),
        tuple(quotas),
    )


@dataclass(frozen=True, slots=True)
class TypedLink:
    left: str
    right: str
    kind: Literal["semantic", "causal"]
    weight: float


@dataclass(frozen=True, slots=True)
class LinkExpansionScore:
    item_id: str
    shared_entities: tuple[str, ...]
    entity_score: float
    semantic_score: float
    causal_score: float

    @property
    def score(self) -> float:
        return self.entity_score + self.semantic_score + self.causal_score


def expand_typed_links(
    seeds: Iterable[str],
    *,
    entity_members: Mapping[str, Sequence[str]],
    links: Iterable[TypedLink],
    allowed_ids: Iterable[str],
    per_entity_limit: int = 200,
    limit: int | None = None,
    include_seeds: bool = False,
) -> tuple[LinkExpansionScore, ...]:
    """Hindsight-style entity/semantic/causal signal accumulation.

    Entity signal is tanh(.5 * distinct shared entity count); semantic and
    causal signals are max supplied weights, summed across the three arms.
    Edges are considered in both directions. Per-entity member ordering is
    caller-supplied, after authorization filtering and occurrence deduplication.
    """
    if per_entity_limit < 0 or (limit is not None and limit < 0):
        raise ValueError("nonnegative limits required")
    allowed = set(allowed_ids)
    seed_set = set(seeds) & allowed
    shared: dict[str, set[str]] = {}
    semantic: dict[str, float] = {}
    causal: dict[str, float] = {}
    for entity, members in entity_members.items():
        if not seed_set.intersection(members):
            continue
        visible = list(
            dict.fromkeys(member for member in members if member in allowed)
        )[:per_entity_limit]
        for member in visible:
            shared.setdefault(member, set()).add(entity)
    for edge in links:
        if (
            edge.kind not in {"semantic", "causal"}
            or not math.isfinite(edge.weight)
            or not 0 <= edge.weight <= 1
        ):
            raise ValueError("known link kind and weight in [0,1] required")
        scores = semantic if edge.kind == "semantic" else causal
        for a, b in ((edge.left, edge.right), (edge.right, edge.left)):
            if a in seed_set and b in allowed:
                scores[b] = max(scores.get(b, 0.0), edge.weight)
    ids = shared.keys() | semantic.keys() | causal.keys()
    result = [
        LinkExpansionScore(
            node,
            tuple(sorted(shared.get(node, ()))),
            math.tanh(0.5 * len(shared.get(node, ()))),
            semantic.get(node, 0.0),
            causal.get(node, 0.0),
        )
        for node in ids
        if include_seeds or node not in seed_set
    ]
    result.sort(key=lambda row: (-row.score, row.item_id))
    return tuple(result if limit is None else result[:limit])


@dataclass(frozen=True, slots=True)
class GraphRerankScore:
    item_id: str
    score: float
    missing: bool = False


def rank_graph_distances(
    candidates: Iterable[str],
    distances: Mapping[str, float],
    *,
    center_score: float = 10.0,
) -> tuple[GraphRerankScore, ...]:
    """Reciprocal true supplied distance; unknown/unreachable nodes score zero.

    An explicit adaptation of Graphiti's adjacency-based default implementation.
    The host can obtain distances with Mari or another shortest-path algorithm.
    """
    if not math.isfinite(center_score) or center_score <= 0:
        raise ValueError("positive center score required")
    rows = []
    for node in dict.fromkeys(candidates):
        distance = distances.get(node, math.inf)
        if math.isnan(distance) or distance < 0:
            raise ValueError("nonnegative distance required")
        rows.append(
            GraphRerankScore(
                node,
                center_score if distance == 0 else 1 / distance,
                not math.isfinite(distance),
            )
        )
    return tuple(sorted(rows, key=lambda row: (-row.score, row.item_id)))


def rank_episode_mentions(
    candidates: Iterable[str], counts: Mapping[str, int], *, ascending: bool = False
) -> tuple[GraphRerankScore, ...]:
    """Rank supplied episodic counts. Missing values sort last in either mode.

    Default descending frequency is explicit; Graphiti's inspected fallback
    uses ascending counts. Missing values are not assigned infinite frequency.
    """
    rows = []
    for node in dict.fromkeys(candidates):
        count = counts.get(node, 0)
        if count < 0:
            raise ValueError("nonnegative mention count required")
        rows.append(GraphRerankScore(node, float(count), node not in counts))
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                row.missing,
                row.score if ascending else -row.score,
                row.item_id,
            ),
        )
    )


@dataclass(frozen=True, slots=True)
class UnionCandidate:
    source: str
    item_id: str
    rank: int
    vector: tuple[float, ...] = ()
    space: str = ""

    def __post_init__(self) -> None:
        if not self.source or not self.item_id or self.rank < 1:
            raise ValueError("source, item ID and one-based rank required")
        object.__setattr__(self, "vector", tuple(self.vector))

    @property
    def key(self) -> tuple[str, str]:
        return self.source, self.item_id


@dataclass(frozen=True, slots=True)
class UnionScore:
    candidate: UnionCandidate
    score: float


def rank_candidate_union(
    candidates: Sequence[UnionCandidate],
    *,
    allowed_keys: Iterable[tuple[str, str]],
    query_vector: Sequence[float] | None = None,
    query_space: str = "",
    union_scores: Mapping[tuple[str, str], float] | None = None,
    limit: int | None = None,
) -> tuple[UnionScore, ...]:
    """Choose common-space cosine or caller-reranked union scores (haiku).

    Supply exactly one scoring mechanism. Ties use within-source rank, then
    source first-arrival order. Duplicate source/item identities are rejected.
    """
    if (query_vector is None) == (union_scores is None) or (
        limit is not None and limit < 0
    ):
        raise ValueError("select exactly one scoring mechanism and nonnegative limit")
    keys = [candidate.key for candidate in candidates]
    if len(set(keys)) != len(keys):
        raise ValueError("source/item identities must be unique")
    allowed = set(allowed_keys)
    visible = [row for row in candidates if row.key in allowed]
    order = {
        source: i
        for i, source in enumerate(dict.fromkeys(row.source for row in visible))
    }
    scores = []
    query = None if query_vector is None else np.asarray(query_vector, dtype=float)
    if query is not None and (
        not query_space
        or query.ndim != 1
        or not len(query)
        or not np.all(np.isfinite(query))
    ):
        raise ValueError("finite query vector and explicit query space required")
    for row in visible:
        if query is not None:
            vector = np.asarray(row.vector, dtype=float)
            if (
                row.space != query_space
                or vector.shape != query.shape
                or not np.all(np.isfinite(vector))
            ):
                raise ValueError("candidate must use the same finite embedding space")
            norm = np.linalg.norm(query) * np.linalg.norm(vector)
            score = float(query @ vector / norm) if norm else 0.0
        else:
            assert union_scores is not None
            score = float(union_scores[row.key])
        if not math.isfinite(score):
            raise ValueError("finite union score required")
        scores.append(UnionScore(row, score))
    scores.sort(
        key=lambda row: (-row.score, row.candidate.rank, order[row.candidate.source])
    )
    return tuple(scores if limit is None else scores[:limit])
