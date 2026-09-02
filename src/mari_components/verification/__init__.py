"""Auditable verification algorithms for generated candidates."""

from .consensus import verdict_consensus
from .models import (
    AttemptFailure,
    ConsensusResult,
    ScoredAttempt,
    SelectionResult,
    VerificationScore,
)
from .portfolio import best_of_n
from .research import (
    AnswerSource,
    ChainOfNoteDecision,
    EvidenceNote,
    SelfRagScore,
    decide_from_evidence_notes,
    score_self_rag_candidate,
)
from .scoring import harmonic_score, idea_completeness, score_grounded
from .selection import select_best

__all__ = [
    "AnswerSource",
    "AttemptFailure",
    "ChainOfNoteDecision",
    "ConsensusResult",
    "EvidenceNote",
    "ScoredAttempt",
    "SelectionResult",
    "SelfRagScore",
    "VerificationScore",
    "best_of_n",
    "decide_from_evidence_notes",
    "harmonic_score",
    "idea_completeness",
    "score_self_rag_candidate",
    "score_grounded",
    "select_best",
    "verdict_consensus",
]
