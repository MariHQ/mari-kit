"""Deterministic memory organization and retrieval policies from research."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class NoteEvolutionPlan:
    """Links and existing notes proposed for contextual evolution."""

    note_id: str
    link_ids: tuple[str, ...]
    evolution_ids: tuple[str, ...]
    scores: tuple[tuple[str, float], ...]


def plan_note_evolution(
    note_id: str,
    similarities: Mapping[str, float],
    *,
    link_threshold: float = 0.7,
    evolution_threshold: float = 0.9,
    limit: int | None = None,
) -> NoteEvolutionPlan:
    """Plan A-MEM links and stronger contextual-evolution candidates.

    Embedding/model scoring and actual metadata edits remain application-owned.
    This boundary makes threshold decisions stable and reviewable.

    Source: Xu et al., "A-MEM: Agentic Memory for LLM Agents"
    (arXiv:2502.12110).
    """
    if not note_id:
        raise ValueError("note_id must not be empty")
    if not 0 <= link_threshold <= evolution_threshold <= 1:
        raise ValueError("thresholds must satisfy 0 <= link <= evolution <= 1")
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")
    rows: list[tuple[str, float]] = []
    for raw_id, raw_score in similarities.items():
        candidate_id = str(raw_id)
        score = float(raw_score)
        if not candidate_id or candidate_id == note_id:
            raise ValueError("candidate IDs must be non-empty and differ from note_id")
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("similarities must be finite values in [0, 1]")
        rows.append((candidate_id, score))
    rows.sort(key=lambda row: (-row[1], row[0]))
    if limit is not None:
        rows = rows[:limit]
    return NoteEvolutionPlan(
        note_id=note_id,
        link_ids=tuple(
            candidate_id for candidate_id, score in rows if score >= link_threshold
        ),
        evolution_ids=tuple(
            candidate_id for candidate_id, score in rows if score >= evolution_threshold
        ),
        scores=tuple(rows),
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class MemorySignal:
    """Raw inputs to the Generative Agents retrieval score."""

    memory_id: str
    hours_since_access: float
    importance: float
    relevance: float


@dataclass(frozen=True, slots=True, kw_only=True)
class SalientMemory:
    """A ranked memory with every normalized score component."""

    memory_id: str
    score: float
    recency: float
    importance: float
    relevance: float


def rank_salient_memories(
    memories: Sequence[MemorySignal],
    *,
    recency_decay: float = 0.995,
    recency_weight: float = 1.0,
    importance_weight: float = 1.0,
    relevance_weight: float = 1.0,
    limit: int | None = None,
) -> tuple[SalientMemory, ...]:
    """Rank memories by normalized recency, importance, and relevance.

    Source: Park et al., "Generative Agents: Interactive Simulacra of Human
    Behavior" (arXiv:2304.03442), retrieval function in section 4.1.
    """
    if not memories:
        return ()
    if not math.isfinite(recency_decay) or not 0 < recency_decay <= 1:
        raise ValueError("recency_decay must be a finite value in (0, 1]")
    weights = (recency_weight, importance_weight, relevance_weight)
    if any(not math.isfinite(value) or value < 0 for value in weights):
        raise ValueError("component weights must be non-negative finite numbers")
    if sum(weights) == 0:
        raise ValueError("at least one component weight must be positive")
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")
    ids = [memory.memory_id for memory in memories]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("memory IDs must be non-empty and unique")
    for memory in memories:
        values = (memory.hours_since_access, memory.importance, memory.relevance)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("memory signals must be finite")
        if memory.hours_since_access < 0:
            raise ValueError("hours_since_access must not be negative")

    recencies = [recency_decay**memory.hours_since_access for memory in memories]
    importances = [memory.importance for memory in memories]
    relevances = [memory.relevance for memory in memories]

    def normalize(values: Sequence[float]) -> list[float]:
        low, high = min(values), max(values)
        if low == high:
            return [1.0] * len(values)
        return [(value - low) / (high - low) for value in values]

    normalized = zip(
        memories,
        normalize(recencies),
        normalize(importances),
        normalize(relevances),
        strict=True,
    )
    hits = [
        SalientMemory(
            memory_id=memory.memory_id,
            score=(
                recency_weight * recency
                + importance_weight * importance
                + relevance_weight * relevance
            ),
            recency=recency,
            importance=importance,
            relevance=relevance,
        )
        for memory, recency, importance, relevance in normalized
    ]
    hits.sort(key=lambda hit: (-hit.score, hit.memory_id))
    return tuple(hits if limit is None else hits[:limit])
