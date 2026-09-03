"""Dependency-light reference indexes with authorization-aware search."""

from __future__ import annotations

import hashlib
import heapq
import math
import re
from collections import Counter
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy import typing as npt


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexHit:
    document_id: str
    score: float


class IndexOperation(StrEnum):
    UPSERT = "upsert"
    DELETE = "delete"


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexDelta:
    item_id: str
    operation: IndexOperation
    revision: str = ""
    text: str = ""
    expected_revision: str | None = None

    def __post_init__(self) -> None:
        if not self.item_id.strip():
            raise ValueError("index delta item ID is required")
        if self.operation is IndexOperation.UPSERT and not self.revision:
            raise ValueError("index upserts require a revision")


def _default_analyzer(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"\w+", text.casefold()))


@dataclass(frozen=True, slots=True, kw_only=True)
class BM25TermContribution:
    term: str
    term_frequency: int
    inverse_document_frequency: float
    score: float


@dataclass(frozen=True, slots=True, kw_only=True)
class BM25Explanation:
    item_id: str
    score: float
    contributions: tuple[BM25TermContribution, ...]


def _matrix(
    vectors: Mapping[str, Sequence[float]],
) -> tuple[tuple[str, ...], npt.NDArray[np.float32]]:
    if not vectors:
        raise ValueError("at least one vector is required")
    ids = tuple(sorted(vectors))
    if any(not identifier for identifier in ids):
        raise ValueError("vector IDs must not be empty")
    matrix = np.asarray([vectors[identifier] for identifier in ids], dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[1] == 0 or not np.all(np.isfinite(matrix)):
        raise ValueError("vectors must form a finite non-empty matrix")
    return ids, matrix


def _query(value: Sequence[float], dimension: int) -> npt.NDArray[np.float32]:
    query = np.asarray(value, dtype=np.float32)
    if query.shape != (dimension,) or not np.all(np.isfinite(query)):
        raise ValueError("query must be a finite vector matching the index dimension")
    return query


class DenseFlatIndex:
    """Exact cosine, dot-product, or negative-L2 baseline."""

    def __init__(
        self, vectors: Mapping[str, Sequence[float]], *, metric: str = "cosine"
    ) -> None:
        if metric not in {"cosine", "dot", "l2"}:
            raise ValueError("metric must be cosine, dot, or l2")
        self.ids, self.vectors = _matrix(vectors)
        self.metric = metric
        if metric == "cosine":
            norms = np.linalg.norm(self.vectors, axis=1)
            if np.any(norms == 0):
                raise ValueError("cosine vectors must be non-zero")
            self.vectors = self.vectors / norms[:, None]

    def search(
        self,
        query: Sequence[float],
        *,
        limit: int,
        allowed_document_ids: Collection[str] | None = None,
    ) -> tuple[IndexHit, ...]:
        if limit < 0:
            raise ValueError("limit must not be negative")
        value = _query(query, self.vectors.shape[1])
        if self.metric == "cosine":
            norm = float(np.linalg.norm(value))
            if norm == 0:
                raise ValueError("cosine query must be non-zero")
            value = value / norm
        allowed = None if allowed_document_ids is None else set(allowed_document_ids)
        positions = [
            index
            for index, identifier in enumerate(self.ids)
            if allowed is None or identifier in allowed
        ]
        selected = self.vectors[positions]
        scores = (
            selected @ value
            if self.metric != "l2"
            else -np.sum((selected - value) ** 2, axis=1)
        )
        hits = [
            IndexHit(document_id=self.ids[index], score=float(score))
            for index, score in zip(positions, scores, strict=True)
        ]
        return tuple(
            sorted(hits, key=lambda hit: (-hit.score, hit.document_id))[:limit]
        )


class SparseVectorIndex:
    """Exact inner-product search over caller-produced sparse term weights."""

    def __init__(self, vectors: Mapping[str, Mapping[str, float]]) -> None:
        if not vectors:
            raise ValueError("at least one sparse vector is required")
        self.vectors = {
            identifier: {
                term: float(weight) for term, weight in vector.items() if weight != 0
            }
            for identifier, vector in vectors.items()
        }
        if any(
            not identifier or not vector for identifier, vector in self.vectors.items()
        ):
            raise ValueError("sparse IDs and vectors must not be empty")
        if any(
            not term or not math.isfinite(weight)
            for vector in self.vectors.values()
            for term, weight in vector.items()
        ):
            raise ValueError("sparse terms and weights must be non-empty and finite")

    def search(
        self,
        query: Mapping[str, float],
        *,
        limit: int,
        allowed_document_ids: Collection[str] | None = None,
    ) -> tuple[IndexHit, ...]:
        if limit < 0:
            raise ValueError("limit must not be negative")
        query_values = {
            term: float(weight) for term, weight in query.items() if weight != 0
        }
        if any(
            not term or not math.isfinite(weight)
            for term, weight in query_values.items()
        ):
            raise ValueError("query terms and weights must be non-empty and finite")
        allowed = None if allowed_document_ids is None else set(allowed_document_ids)
        hits = (
            IndexHit(
                document_id=identifier,
                score=sum(
                    query_values.get(term, 0.0) * weight
                    for term, weight in vector.items()
                ),
            )
            for identifier, vector in self.vectors.items()
            if allowed is None or identifier in allowed
        )
        return tuple(
            sorted(hits, key=lambda hit: (-hit.score, hit.document_id))[:limit]
        )


class BM25Index:
    """Robertson--Walker BM25 with deterministic tokenization and tie-breaking."""

    def __init__(
        self,
        documents: Mapping[str, str],
        *,
        k1: float = 1.2,
        b: float = 0.75,
        analyzer: Callable[[str], Iterable[str]] | None = None,
        revisions: Mapping[str, str] | None = None,
    ) -> None:
        if not math.isfinite(k1) or k1 < 0 or not math.isfinite(b) or not 0 <= b <= 1:
            raise ValueError("valid BM25 k1/b parameters are required")
        if revisions is not None and set(revisions) != set(documents):
            raise ValueError("BM25 revisions must match document IDs")
        self.k1, self.b = k1, b
        self.documents = dict(documents)
        self.revisions = dict(revisions or {identifier: "" for identifier in documents})
        self.analyzer = analyzer or _default_analyzer
        self.tokens = {
            identifier: tuple(self.analyzer(text))
            for identifier, text in documents.items()
        }
        if any(not identifier for identifier in self.tokens) or any(
            not term for tokens in self.tokens.values() for term in tokens
        ):
            raise ValueError("document IDs and analyzer terms must not be empty")
        self.lengths = {
            identifier: len(tokens) for identifier, tokens in self.tokens.items()
        }
        self.average_length = (
            sum(self.lengths.values()) / len(self.lengths) if self.lengths else 0.0
        )
        frequency: Counter[str] = Counter()
        for tokens in self.tokens.values():
            frequency.update(set(tokens))
        count = len(self.tokens)
        self.idf = {
            term: math.log(1 + (count - value + 0.5) / (value + 0.5))
            for term, value in frequency.items()
        }

    def search(
        self,
        query: str,
        *,
        limit: int,
        allowed_document_ids: Collection[str] | None = None,
    ) -> tuple[IndexHit, ...]:
        if limit < 0:
            raise ValueError("limit must not be negative")
        terms = tuple(self.analyzer(query))
        allowed = None if allowed_document_ids is None else set(allowed_document_ids)
        hits: list[IndexHit] = []
        for identifier in self.tokens:
            if allowed is not None and identifier not in allowed:
                continue
            contributions = self._contributions(identifier, terms)
            hits.append(
                IndexHit(
                    document_id=identifier,
                    score=sum(item.score for item in contributions),
                )
            )
        return tuple(
            sorted(hits, key=lambda hit: (-hit.score, hit.document_id))[:limit]
        )

    def explain(self, query: str, *, item_id: str) -> BM25Explanation:
        """Return per-query-term contributions for one indexed item."""

        if item_id not in self.tokens:
            raise KeyError(item_id)
        contributions = self._contributions(item_id, tuple(self.analyzer(query)))
        return BM25Explanation(
            item_id=item_id,
            score=sum(item.score for item in contributions),
            contributions=contributions,
        )

    def _contributions(
        self, item_id: str, terms: Sequence[str]
    ) -> tuple[BM25TermContribution, ...]:
        frequencies = Counter(self.tokens[item_id])
        result: list[BM25TermContribution] = []
        for term in terms:
            term_frequency = frequencies[term]
            denominator = term_frequency + self.k1 * (
                1 - self.b + self.b * self.lengths[item_id] / (self.average_length or 1)
            )
            contribution = (
                self.idf.get(term, 0.0) * term_frequency * (self.k1 + 1) / denominator
                if term_frequency
                else 0.0
            )
            result.append(
                BM25TermContribution(
                    term=term,
                    term_frequency=term_frequency,
                    inverse_document_frequency=self.idf.get(term, 0.0),
                    score=contribution,
                )
            )
        return tuple(result)

    def with_deltas(self, deltas: Iterable[IndexDelta]) -> BM25Index:
        """Build a new lexical snapshot after revision-checked item changes."""

        documents = dict(self.documents)
        revisions = dict(self.revisions)
        for delta in deltas:
            current = revisions.get(delta.item_id)
            if (
                delta.expected_revision is not None
                and current != delta.expected_revision
            ):
                raise ValueError(
                    f"revision mismatch for {delta.item_id!r}: "
                    f"expected {delta.expected_revision!r}, found {current!r}"
                )
            if delta.operation is IndexOperation.DELETE:
                documents.pop(delta.item_id, None)
                revisions.pop(delta.item_id, None)
            else:
                documents[delta.item_id] = delta.text
                revisions[delta.item_id] = delta.revision
        return BM25Index(
            documents,
            k1=self.k1,
            b=self.b,
            analyzer=self.analyzer,
            revisions=revisions,
        )


class HNSWIndex:
    """Deterministic HNSW topology with exact construction neighbors."""

    def __init__(
        self,
        vectors: Mapping[str, Sequence[float]],
        *,
        m: int = 16,
        metric: str = "cosine",
    ) -> None:
        if m < 2:
            raise ValueError("m must be at least two")
        self.flat = DenseFlatIndex(vectors, metric=metric)
        self.m = m
        self.levels = {
            identifier: self._level(identifier) for identifier in self.flat.ids
        }
        self.max_level = max(self.levels.values())
        self.entry = min(
            identifier
            for identifier, level in self.levels.items()
            if level == self.max_level
        )
        self.graph: dict[tuple[int, str], tuple[str, ...]] = {}
        positions = {
            identifier: index for index, identifier in enumerate(self.flat.ids)
        }
        for level in range(self.max_level + 1):
            active = [
                identifier
                for identifier in self.flat.ids
                if self.levels[identifier] >= level
            ]
            for identifier in active:
                vector = self.flat.vectors[positions[identifier]]
                neighbors = sorted(
                    (other for other in active if other != identifier),
                    key=lambda other: (
                        -self._score(vector, self.flat.vectors[positions[other]]),
                        other,
                    ),
                )[:m]
                self.graph[level, identifier] = tuple(neighbors)

    @staticmethod
    def _level(identifier: str) -> int:
        value = int.from_bytes(hashlib.sha256(identifier.encode()).digest()[:8], "big")
        level = 0
        while level < 16 and value & 1:
            level += 1
            value >>= 1
        return level

    def _score(
        self, left: npt.NDArray[np.float32], right: npt.NDArray[np.float32]
    ) -> float:
        return (
            float(left @ right)
            if self.flat.metric != "l2"
            else -float(np.sum((left - right) ** 2))
        )

    def search(
        self,
        query: Sequence[float],
        *,
        limit: int,
        ef_search: int = 64,
        allowed_document_ids: Collection[str] | None = None,
    ) -> tuple[IndexHit, ...]:
        if limit < 0 or ef_search < max(1, limit):
            raise ValueError("ef_search must be positive and at least limit")
        value = _query(query, self.flat.vectors.shape[1])
        if self.flat.metric == "cosine":
            norm = float(np.linalg.norm(value))
            if norm == 0:
                raise ValueError("cosine query must be non-zero")
            value = value / norm
        positions = {
            identifier: index for index, identifier in enumerate(self.flat.ids)
        }
        allowed = (
            set(self.flat.ids)
            if allowed_document_ids is None
            else set(allowed_document_ids) & set(self.flat.ids)
        )
        if not allowed or limit == 0:
            return ()
        search_level = max(self.levels[identifier] for identifier in allowed)
        current = min(
            identifier
            for identifier in allowed
            if self.levels[identifier] == search_level
        )
        current_score = self._score(value, self.flat.vectors[positions[current]])
        for level in range(search_level, 0, -1):
            improved = True
            while improved:
                improved = False
                for neighbor in self.graph.get((level, current), ()):
                    if neighbor not in allowed:
                        continue
                    score = self._score(value, self.flat.vectors[positions[neighbor]])
                    if (score, neighbor) > (current_score, current):
                        current, current_score, improved = neighbor, score, True
        frontier = [(-current_score, current)]
        visited = {current}
        scored: dict[str, float] = {current: current_score}
        while frontier and len(visited) < ef_search:
            _negative, identifier = heapq.heappop(frontier)
            for neighbor in self.graph.get((0, identifier), ()):
                if neighbor in visited or neighbor not in allowed:
                    continue
                visited.add(neighbor)
                score = self._score(value, self.flat.vectors[positions[neighbor]])
                scored[neighbor] = score
                heapq.heappush(frontier, (-score, neighbor))
        hits = [
            IndexHit(document_id=identifier, score=score)
            for identifier, score in scored.items()
        ]
        return tuple(
            sorted(hits, key=lambda hit: (-hit.score, hit.document_id))[:limit]
        )


def _kmeans(
    values: npt.NDArray[np.float32], clusters: int, iterations: int
) -> npt.NDArray[np.float32]:
    if clusters < 1 or clusters > len(values):
        raise ValueError("cluster count must be between one and the training size")
    centroids = values[np.linspace(0, len(values) - 1, clusters, dtype=int)].copy()
    for _ in range(iterations):
        assignments = np.argmin(
            np.sum((values[:, None, :] - centroids[None, :, :]) ** 2, axis=2), axis=1
        )
        updated = centroids.copy()
        for cluster in range(clusters):
            members = values[assignments == cluster]
            if len(members):
                updated[cluster] = np.mean(members, axis=0)
        if np.allclose(updated, centroids):
            break
        centroids = updated
    return centroids


class IVFPQIndex:
    """Deterministic IVF with residual product-quantized L2 search."""

    def __init__(
        self,
        vectors: Mapping[str, Sequence[float]],
        *,
        partitions: int,
        subquantizers: int,
        codebook_size: int = 16,
        iterations: int = 20,
    ) -> None:
        self.ids, values = _matrix(vectors)
        if partitions < 1 or partitions > len(values):
            raise ValueError("partitions must be between one and the vector count")
        if subquantizers < 1 or values.shape[1] % subquantizers:
            raise ValueError("subquantizers must divide the vector dimension")
        if codebook_size < 1 or iterations < 1:
            raise ValueError("codebook_size and iterations must be positive")
        self.dimension = values.shape[1]
        self.subquantizers = subquantizers
        self.width = self.dimension // subquantizers
        self.coarse = _kmeans(values, partitions, iterations)
        coarse_assignments = np.argmin(
            np.sum((values[:, None, :] - self.coarse[None, :, :]) ** 2, axis=2), axis=1
        )
        residuals = values - self.coarse[coarse_assignments]
        selected_size = min(codebook_size, len(values))
        self.codebooks = tuple(
            _kmeans(residuals[:, start : start + self.width], selected_size, iterations)
            for start in range(0, self.dimension, self.width)
        )
        codes = np.empty((len(values), subquantizers), dtype=np.int32)
        for part, codebook in enumerate(self.codebooks):
            start = part * self.width
            subspace = residuals[:, start : start + self.width]
            codes[:, part] = np.argmin(
                np.sum((subspace[:, None, :] - codebook[None, :, :]) ** 2, axis=2),
                axis=1,
            )
        self.codes = codes
        self.assignments = coarse_assignments

    def search(
        self,
        query: Sequence[float],
        *,
        limit: int,
        probes: int = 1,
        allowed_document_ids: Collection[str] | None = None,
    ) -> tuple[IndexHit, ...]:
        if limit < 0 or probes < 1 or probes > len(self.coarse):
            raise ValueError(
                "limit must be non-negative and probes must address existing partitions"
            )
        value = _query(query, self.dimension)
        coarse_distances = np.sum((self.coarse - value) ** 2, axis=1)
        selected_partitions = set(
            np.argsort(coarse_distances, kind="stable")[:probes].tolist()
        )
        allowed = None if allowed_document_ids is None else set(allowed_document_ids)
        hits: list[IndexHit] = []
        for index, identifier in enumerate(self.ids):
            if int(self.assignments[index]) not in selected_partitions or (
                allowed is not None and identifier not in allowed
            ):
                continue
            reconstructed = self.coarse[self.assignments[index]].copy()
            for part, codebook in enumerate(self.codebooks):
                start = part * self.width
                reconstructed[start : start + self.width] += codebook[
                    self.codes[index, part]
                ]
            hits.append(
                IndexHit(
                    document_id=identifier,
                    score=-float(np.sum((reconstructed - value) ** 2)),
                )
            )
        return tuple(
            sorted(hits, key=lambda hit: (-hit.score, hit.document_id))[:limit]
        )
