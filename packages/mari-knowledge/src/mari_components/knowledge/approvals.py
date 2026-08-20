"""Deterministic automated-approval policy using immutable actor identifiers."""

from __future__ import annotations

from dataclasses import dataclass


POLICY_VERSION = "approval-v2"


@dataclass(frozen=True, slots=True)
class ReviewItem:
    identifier: str
    kind: str
    proposer_id: str = ""
    confidence: float = 0.0
    evidence_count: int = 0
    trusted_source: bool = False


@dataclass(frozen=True, slots=True)
class ApprovalPolicy:
    minimum_confidence: float = 0.9
    minimum_evidence: int = 2
    allowed_kinds: frozenset[str] = frozenset({"fact", "decision", "answer"})
    require_separate_reviewer: bool = True
    version: str = POLICY_VERSION


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    item_id: str
    outcome: str
    explanation: str
    policy_version: str


def evaluate_approval(item: ReviewItem, reviewer_id: str, policy: ApprovalPolicy | None = None) -> PolicyDecision:
    selected = policy or ApprovalPolicy()
    if not reviewer_id:
        return PolicyDecision(item.identifier, "deny", "A reviewer id is required.", selected.version)
    if selected.require_separate_reviewer and item.proposer_id and item.proposer_id == reviewer_id:
        return PolicyDecision(item.identifier, "deny", "The proposer cannot approve the same item.", selected.version)
    reasons: list[str] = []
    if item.kind not in selected.allowed_kinds:
        reasons.append(f"{item.kind} is not eligible for automatic approval")
    if item.confidence < selected.minimum_confidence:
        reasons.append(f"confidence {item.confidence:.2f} is below {selected.minimum_confidence:.2f}")
    if item.evidence_count < selected.minimum_evidence:
        reasons.append(f"evidence count {item.evidence_count} is below {selected.minimum_evidence}")
    if not item.trusted_source:
        reasons.append("the source is not trusted for automatic approval")
    if reasons:
        return PolicyDecision(item.identifier, "manual", "; ".join(reasons).capitalize() + ".", selected.version)
    return PolicyDecision(item.identifier, "allow", "The item meets the configured automatic-approval policy.", selected.version)
