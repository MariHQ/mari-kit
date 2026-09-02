"""Storage-neutral rank fusion and diversity-aware selection."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class RankContribution:
    """One ranked list's auditable contribution to a fused result."""

    source: str
    rank: int
    weight: float
    score: float


@dataclass(frozen=True, slots=True, kw_only=True)
class FusedHit:
    """A document ranked by reciprocal-rank fusion."""

    document_id: str
    score: float
    contributions: tuple[RankContribution, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class DiversifiedHit:
    """One greedy maximal-marginal-relevance selection step."""

    document_id: str
    score: float
    relevance: float
    redundancy: float


def reciprocal_rank_fusion(
    rankings: Mapping[str, Iterable[str]],
    *,
    rank_constant: float = 60.0,
    weights: Mapping[str, float] | None = None,
    limit: int | None = None,
    eligible: Callable[[str], bool] | None = None,
) -> tuple[FusedHit, ...]:
    """Fuse independent ranked lists using ``weight / (rank_constant + rank)``.

    Ranks are one-based. A document contributes at most once per source, so a
    malformed source cannot inflate its score with duplicates. ``eligible`` is
    applied before scoring and is intended for caller-owned ACL or scope rules.
    """
    if not math.isfinite(rank_constant) or rank_constant <= 0:
        raise ValueError("rank_constant must be a positive finite number")
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")

    known_weights = dict(weights or {})
    unknown = set(known_weights) - set(rankings)
    if unknown:
        raise ValueError(
            f"weights contain unknown ranking sources: {sorted(unknown)!r}"
        )

    totals: dict[str, float] = {}
    details: dict[str, list[RankContribution]] = {}
    for source, ranking in rankings.items():
        weight = float(known_weights.get(source, 1.0))
        if not math.isfinite(weight) or weight <= 0:
            raise ValueError("ranking weights must be positive finite numbers")
        seen: set[str] = set()
        for rank, raw_id in enumerate(ranking, start=1):
            document_id = str(raw_id)
            if not document_id or document_id in seen:
                continue
            seen.add(document_id)
            if eligible is not None and not eligible(document_id):
                continue
            contribution = weight / (rank_constant + rank)
            totals[document_id] = totals.get(document_id, 0.0) + contribution
            details.setdefault(document_id, []).append(
                RankContribution(
                    source=str(source),
                    rank=rank,
                    weight=weight,
                    score=contribution,
                )
            )

    ordered = sorted(
        totals, key=lambda document_id: (-totals[document_id], document_id)
    )
    if limit is not None:
        ordered = ordered[:limit]
    return tuple(
        FusedHit(
            document_id=document_id,
            score=totals[document_id],
            contributions=tuple(details[document_id]),
        )
        for document_id in ordered
    )


def maximal_marginal_relevance(
    relevance: Mapping[str, float],
    similarity: Callable[[str, str], float],
    *,
    limit: int,
    relevance_weight: float = 0.5,
) -> tuple[DiversifiedHit, ...]:
    """Greedily balance query relevance against redundancy with selected hits.

    At each step the score is ``lambda * relevance - (1-lambda) * max_similarity``.
    Similarity is caller supplied, keeping the policy independent of an embedding
    provider or index. Scores and similarity values must be finite.
    """
    if limit < 1:
        raise ValueError("limit must be positive")
    if not math.isfinite(relevance_weight) or not 0 <= relevance_weight <= 1:
        raise ValueError("relevance_weight must be a finite value in [0, 1]")

    remaining: dict[str, float] = {}
    for raw_id, raw_score in relevance.items():
        document_id = str(raw_id)
        score = float(raw_score)
        if not document_id:
            raise ValueError("document IDs must not be empty")
        if not math.isfinite(score):
            raise ValueError("relevance scores must be finite")
        remaining[document_id] = score

    selected: list[DiversifiedHit] = []
    while remaining and len(selected) < limit:
        choices: list[tuple[float, float, str]] = []
        redundancies: dict[str, float] = {}
        for document_id, query_score in remaining.items():
            redundancy = 0.0
            if selected:
                values = [
                    float(similarity(document_id, hit.document_id)) for hit in selected
                ]
                if any(not math.isfinite(value) for value in values):
                    raise ValueError("similarity scores must be finite")
                redundancy = max(values)
            score = relevance_weight * query_score - (1 - relevance_weight) * redundancy
            redundancies[document_id] = redundancy
            choices.append((score, query_score, document_id))
        score, query_score, document_id = min(
            choices,
            key=lambda row: (-row[0], -row[1], row[2]),
        )
        selected.append(
            DiversifiedHit(
                document_id=document_id,
                score=score,
                relevance=query_score,
                redundancy=redundancies[document_id],
            )
        )
        del remaining[document_id]
    return tuple(selected)
