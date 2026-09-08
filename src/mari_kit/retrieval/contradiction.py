"""Sparse embedding operations for efficient contradiction retrieval."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np
from numpy import typing as npt

FloatArray = npt.NDArray[np.floating]


def _vector(value: FloatArray, *, name: str) -> npt.NDArray[np.float64]:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 1 or array.size < 2:
        raise ValueError(f"{name} must be a vector with at least two dimensions")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    return array


def _paired_vectors(
    first: FloatArray,
    second: FloatArray,
    *,
    first_name: str = "first embedding",
    second_name: str = "second embedding",
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    left = _vector(first, name=first_name)
    right = _vector(second, name=second_name)
    if left.shape != right.shape:
        raise ValueError("embedding dimensions must match")
    return left, right


def hoyer_difference_sparsity(first: FloatArray, second: FloatArray) -> float:
    """Return Hoyer sparsity of the difference between two embeddings.

    SparseCL trains an encoder so contradictions differ in a small semantic
    subspace. The normalized Hoyer measure is zero for a dense difference and
    one for a one-coordinate difference. Identical vectors have no
    contradiction-bearing difference and are assigned zero.

    Source: Xu et al., "SparseCL" (arXiv:2406.10746), Equation 1.
    """
    left, right = _paired_vectors(first, second)
    difference = left - right
    l2_norm = float(np.linalg.norm(difference, ord=2))
    if l2_norm == 0:
        return 0.0
    dimension = difference.size
    root_dimension = math.sqrt(dimension)
    l1_norm = float(np.linalg.norm(difference, ord=1))
    value = (root_dimension - (l1_norm / l2_norm)) / (root_dimension - 1.0)
    return min(1.0, max(0.0, value))


def _cosine_similarity(first: FloatArray, second: FloatArray) -> float:
    left, right = _paired_vectors(first, second)
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator == 0:
        raise ValueError("cosine embeddings must be non-zero")
    return min(1.0, max(-1.0, float(np.dot(left, right) / denominator)))


@dataclass(frozen=True, slots=True, kw_only=True)
class SparseContradictionScore:
    """Inspectable components of SparseCL inference scoring."""

    cosine_similarity: float
    difference_sparsity: float
    alpha: float
    score: float


def sparse_contradiction_score(
    query_similarity_embedding: FloatArray,
    passage_similarity_embedding: FloatArray,
    query_sparse_embedding: FloatArray,
    passage_sparse_embedding: FloatArray,
    *,
    alpha: float,
) -> SparseContradictionScore:
    """Combine cosine similarity and sparse difference as in SparseCL.

    The similarity embeddings come from the ordinary retrieval encoder E; the
    sparse embeddings come from the separately SparseCL-trained encoder E_s.

    Source: Xu et al., "SparseCL" (arXiv:2406.10746), Equation 3.
    """
    weight = float(alpha)
    if not math.isfinite(weight) or weight < 0:
        raise ValueError("alpha must be a finite non-negative number")
    cosine = _cosine_similarity(
        query_similarity_embedding, passage_similarity_embedding
    )
    sparsity = hoyer_difference_sparsity(
        query_sparse_embedding, passage_sparse_embedding
    )
    return SparseContradictionScore(
        cosine_similarity=cosine,
        difference_sparsity=sparsity,
        alpha=weight,
        score=cosine + weight * sparsity,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class SparseContradictionCandidate:
    """One corpus passage represented by both SparseCL encoder paths."""

    passage_id: str
    similarity_embedding: FloatArray
    sparse_embedding: FloatArray


@dataclass(frozen=True, slots=True, kw_only=True)
class SparseContradictionHit:
    """One contradiction candidate with its complete reranking trace."""

    passage_id: str
    rank: int
    cosine_similarity: float
    difference_sparsity: float
    score: float


def rank_sparse_contradictions(
    query_similarity_embedding: FloatArray,
    query_sparse_embedding: FloatArray,
    candidates: Iterable[SparseContradictionCandidate],
    *,
    alpha: float,
    limit: int = 10,
    candidate_limit: int | None = 1000,
    allowed_passage_ids: Iterable[str] | None = None,
) -> tuple[SparseContradictionHit, ...]:
    """Prefilter by cosine, then rerank by the SparseCL combined score.

    Authorization is applied before either score is calculated. The paper uses
    a large cosine candidate set (for example 1,000) before sparse reranking;
    ``None`` scores the complete allowed corpus.

    Source: Xu et al., "SparseCL" (arXiv:2406.10746), Section 3.
    """
    if limit < 1:
        raise ValueError("limit must be positive")
    if candidate_limit is not None and candidate_limit < limit:
        raise ValueError("candidate_limit must be at least limit or None")
    weight = float(alpha)
    if not math.isfinite(weight) or weight < 0:
        raise ValueError("alpha must be a finite non-negative number")
    _vector(query_similarity_embedding, name="query similarity embedding")
    _vector(query_sparse_embedding, name="query sparse embedding")
    allowed = None if allowed_passage_ids is None else set(allowed_passage_ids)
    rows = tuple(candidates)
    ids = [row.passage_id for row in rows]
    if any(not passage_id for passage_id in ids) or len(ids) != len(set(ids)):
        raise ValueError("passage IDs must be non-empty and unique")
    authorized = [row for row in rows if allowed is None or row.passage_id in allowed]

    cosine_rows = [
        (
            _cosine_similarity(
                query_similarity_embedding, candidate.similarity_embedding
            ),
            candidate,
        )
        for candidate in authorized
    ]
    cosine_rows.sort(key=lambda row: (-row[0], row[1].passage_id))
    if candidate_limit is not None:
        cosine_rows = cosine_rows[:candidate_limit]

    scored: list[tuple[SparseContradictionScore, str]] = []
    for _, candidate in cosine_rows:
        result = sparse_contradiction_score(
            query_similarity_embedding,
            candidate.similarity_embedding,
            query_sparse_embedding,
            candidate.sparse_embedding,
            alpha=weight,
        )
        scored.append((result, candidate.passage_id))
    scored.sort(key=lambda row: (-row[0].score, row[1]))
    return tuple(
        SparseContradictionHit(
            passage_id=passage_id,
            rank=rank,
            cosine_similarity=result.cosine_similarity,
            difference_sparsity=result.difference_sparsity,
            score=result.score,
        )
        for rank, (result, passage_id) in enumerate(scored[:limit], start=1)
    )


def sparse_contrastive_losses(
    anchors: Sequence[FloatArray],
    contradictions: Sequence[FloatArray],
    similar_negatives: Sequence[FloatArray],
    *,
    temperature: float,
) -> npt.NDArray[np.float32]:
    """Evaluate SparseCL's Hoyer contrastive objective per training example.

    This NumPy implementation is a conformance oracle, not an autodiff trainer.
    Contradictions are positives; similar passages are hard negatives; other
    batch items supply soft negatives through the shared denominator.

    Source: Xu et al., "SparseCL" (arXiv:2406.10746), Equation 2.
    """
    if (
        not anchors
        or len(anchors) != len(contradictions)
        or len(anchors) != len(similar_negatives)
    ):
        raise ValueError("anchor, contradiction, and negative batches must match")
    tau = float(temperature)
    if not math.isfinite(tau) or tau <= 0:
        raise ValueError("temperature must be a positive finite number")
    anchor_rows = [_vector(value, name="anchor") for value in anchors]
    positive_rows = [_vector(value, name="contradiction") for value in contradictions]
    negative_rows = [
        _vector(value, name="similar negative") for value in similar_negatives
    ]
    shape = anchor_rows[0].shape
    if any(
        row.shape != shape for row in (*anchor_rows, *positive_rows, *negative_rows)
    ):
        raise ValueError("all training embeddings must have equal dimensions")

    losses: list[float] = []
    for index, anchor in enumerate(anchor_rows):
        positive_logits = np.asarray(
            [hoyer_difference_sparsity(anchor, row) / tau for row in positive_rows],
            dtype=np.float64,
        )
        negative_logits = np.asarray(
            [hoyer_difference_sparsity(anchor, row) / tau for row in negative_rows],
            dtype=np.float64,
        )
        logits = np.concatenate((positive_logits, negative_logits))
        maximum = float(np.max(logits))
        log_denominator = maximum + math.log(float(np.exp(logits - maximum).sum()))
        losses.append(log_denominator - float(positive_logits[index]))
    return np.asarray(losses, dtype=np.float32)
