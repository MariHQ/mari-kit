"""Auditable verification algorithms for generated candidates."""

from .consensus import verdict_consensus
from .contradiction import (
    DocumentContradictionAssessment,
    DocumentContradictionRewards,
    document_contradiction_rewards,
    reasoning_sentence_references,
    validate_document_contradiction,
)
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
    "DocumentContradictionAssessment",
    "DocumentContradictionRewards",
    "EvidenceNote",
    "ScoredAttempt",
    "SelectionResult",
    "SelfRagScore",
    "VerificationScore",
    "best_of_n",
    "decide_from_evidence_notes",
    "document_contradiction_rewards",
    "harmonic_score",
    "idea_completeness",
    "score_self_rag_candidate",
    "score_grounded",
    "select_best",
    "reasoning_sentence_references",
    "validate_document_contradiction",
    "verdict_consensus",
]
