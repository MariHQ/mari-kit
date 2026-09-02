"""Evidence-aware consensus for repeated fact assessments."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

from mari_components.knowledge import FactAssessment, normalize_claim

from .models import ConsensusResult


def verdict_consensus(
    assessments: Iterable[FactAssessment],
    *,
    weights: Sequence[float] | None = None,
    minimum_agreement: float = 0.5,
) -> ConsensusResult:
    """Combine assessments, abstaining on ties or weak agreement."""
    rows = tuple(assessments)
    if not rows:
        raise ValueError("consensus requires at least one assessment")
    if not 0 <= minimum_agreement <= 1:
        raise ValueError("minimum agreement must be in [0, 1]")
    claim_key = normalize_claim(rows[0].claim)
    if not claim_key or any(normalize_claim(row.claim) != claim_key for row in rows):
        raise ValueError("consensus assessments must address the same claim")
    vote_weights = tuple(1.0 for _ in rows) if weights is None else tuple(weights)
    if len(vote_weights) != len(rows):
        raise ValueError("weights must match assessments")
    if any(weight < 0 or not math.isfinite(weight) for weight in vote_weights):
        raise ValueError("weights must be finite and non-negative")
    total = sum(vote_weights)
    if total <= 0:
        raise ValueError("at least one weight must be positive")

    votes = {"supported": 0.0, "contradicted": 0.0, "uncertain": 0.0}
    for row, weight in zip(rows, vote_weights, strict=True):
        votes[row.verdict] += weight
    ordered = sorted(votes, key=lambda verdict: (-votes[verdict], verdict))
    leader, runner_up = ordered[:2]
    agreement = votes[leader] / total
    verdict = (
        leader
        if votes[leader] > votes[runner_up] and agreement >= minimum_agreement
        else "uncertain"
    )

    evidence = []
    seen = set()
    if verdict != "uncertain":
        for row in rows:
            if row.verdict != verdict:
                continue
            for item in row.evidence:
                key = (
                    item.document_id,
                    item.revision,
                    item.start,
                    item.end,
                    item.quote,
                )
                if key not in seen:
                    seen.add(key)
                    evidence.append(item)
    return ConsensusResult(
        claim=rows[0].claim,
        verdict=verdict,
        agreement=round(agreement, 4),
        evidence=tuple(evidence),
        votes=votes,
        assessments=rows,
    )
