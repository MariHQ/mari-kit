"""Deterministic controls around model-produced RAG judgments."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True, kw_only=True)
class SelfRagScore:
    """Self-RAG candidate score with inspectable contributions."""

    score: float
    generation_probability: float
    relevance_contribution: float
    support_contribution: float
    utility_contribution: float
    retrieve: bool


def score_self_rag_candidate(
    *,
    generation_probability: float,
    retrieve_probability: float,
    relevance_probability: float,
    support_probability: float,
    utility: float,
    retrieve_threshold: float = 0.5,
    relevance_weight: float = 1.0,
    support_weight: float = 1.0,
    utility_weight: float = 0.5,
) -> SelfRagScore:
    """Score externally generated Self-RAG reflection signals.

    The host model produces token probabilities; Mari combines them and exposes
    each contribution for selection and audit.

    Source: Asai et al., "Self-RAG" (arXiv:2310.11511), section 3.3.
    """
    probabilities = (retrieve_probability, relevance_probability, support_probability)
    if any(not math.isfinite(value) or not 0 <= value <= 1 for value in probabilities):
        raise ValueError("reflection probabilities must be finite values in [0, 1]")
    if not math.isfinite(generation_probability) or not 0 <= generation_probability <= 1:
        raise ValueError("generation_probability must be a finite value in [0, 1]")
    if not math.isfinite(utility) or not 0 <= utility <= 1:
        raise ValueError("utility must be a finite value in [0, 1]")
    if not 0 <= retrieve_threshold <= 1:
        raise ValueError("retrieve_threshold must be in [0, 1]")
    weights = (relevance_weight, support_weight, utility_weight)
    if any(not math.isfinite(value) or value < 0 for value in weights):
        raise ValueError("reflection weights must be non-negative finite numbers")
    relevance = relevance_weight * relevance_probability
    support = support_weight * support_probability
    utility_contribution = utility_weight * utility
    return SelfRagScore(
        score=generation_probability + relevance + support + utility_contribution,
        generation_probability=generation_probability,
        relevance_contribution=relevance,
        support_contribution=support,
        utility_contribution=utility_contribution,
        retrieve=retrieve_probability >= retrieve_threshold,
    )


class AnswerSource(StrEnum):
    """Knowledge source selected after sequential evidence notes."""

    RETRIEVED = "retrieved"
    PARAMETRIC = "parametric"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceNote:
    """A model-produced Chain-of-Note judgment for one retrieved document."""

    document_id: str
    relevant: bool
    supports_answer: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class ChainOfNoteDecision:
    """Answerability decision and the documents that support it."""

    source: AnswerSource
    relevant_document_ids: tuple[str, ...]
    supporting_document_ids: tuple[str, ...]


def decide_from_evidence_notes(
    notes: Sequence[EvidenceNote],
    *,
    parametric_knowledge_available: bool = False,
) -> ChainOfNoteDecision:
    """Choose retrieved, parametric, or unknown answering after reading notes.

    Source: Yu et al., "Chain-of-Note" (arXiv:2311.09210).
    """
    ids = [note.document_id for note in notes]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("note document IDs must be non-empty and unique")
    if any(note.supports_answer and not note.relevant for note in notes):
        raise ValueError("an answer-supporting note must also be relevant")
    relevant = tuple(note.document_id for note in notes if note.relevant)
    supporting = tuple(note.document_id for note in notes if note.supports_answer)
    if supporting:
        source = AnswerSource.RETRIEVED
    elif parametric_knowledge_available:
        source = AnswerSource.PARAMETRIC
    else:
        source = AnswerSource.UNKNOWN
    return ChainOfNoteDecision(
        source=source,
        relevant_document_ids=relevant,
        supporting_document_ids=supporting,
    )
