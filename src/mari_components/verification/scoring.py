"""Deterministic score breakdowns for grounded Mari values."""

from __future__ import annotations

import re
from collections.abc import Iterable

from mari_components.knowledge import FactAssessment, GroundedAnswer
from mari_components.types import FactCandidate

from .models import VerificationScore

_TOKEN = re.compile(r"[\w]+", re.UNICODE)


def harmonic_score(first: float, second: float) -> float:
    """Return a clamped harmonic mean."""
    left = max(0.0, min(1.0, float(first)))
    right = max(0.0, min(1.0, float(second)))
    return 0.0 if left + right == 0 else 2 * left * right / (left + right)


def idea_completeness(text: str, required_ideas: Iterable[str] = ()) -> float:
    """Measure how many required ideas have all their tokens represented."""
    ideas = tuple(str(idea).strip() for idea in required_ideas if str(idea).strip())
    if not ideas:
        return 1.0
    present = set(_TOKEN.findall(str(text).casefold()))
    covered = 0
    for idea in ideas:
        needed = set(_TOKEN.findall(idea.casefold()))
        covered += bool(needed and needed <= present)
    return covered / len(ideas)


def score_grounded(
    candidate: FactAssessment | FactCandidate | GroundedAnswer,
    *,
    required_ideas: Iterable[str] = (),
) -> VerificationScore:
    """Score one already-parsed value without treating the score as truth probability."""
    if isinstance(candidate, GroundedAnswer):
        text = candidate.answer
        certainty = float(candidate.disposition.value == "grounded")
    elif isinstance(candidate, FactAssessment):
        text = candidate.claim
        certainty = float(candidate.verdict != "uncertain")
    else:
        text = candidate.claim
        certainty = 1.0

    evidence = tuple(candidate.evidence)
    evidence_valid = bool(evidence)
    groundedness = candidate.grounding_coverage if evidence_valid else 0.0
    completeness = idea_completeness(text, required_ideas)
    corroboration = min(len({item.document_id for item in evidence}), 2) / 2
    quality = harmonic_score(groundedness, completeness)
    score = 0.0 if not evidence_valid else quality * (
        0.85 + 0.1 * corroboration + 0.05 * certainty
    )
    return VerificationScore(
        score=round(score, 4),
        groundedness=round(groundedness, 4),
        completeness=round(completeness, 4),
        corroboration=round(corroboration, 4),
        certainty=certainty,
        evidence_valid=evidence_valid,
        checks={
            "evidence": evidence_valid,
            "complete": completeness == 1.0,
            "certain": certainty == 1.0,
        },
    )
