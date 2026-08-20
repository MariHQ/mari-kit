"""Immutable review values with no persistence or transport knowledge."""

from __future__ import annotations

from dataclasses import dataclass


POLICY_VERSION = "review-v1"


@dataclass(frozen=True, slots=True)
class ReviewRecord:
    id: str
    kind: str
    title: str
    status: str
    source: str = ""
    assignee: str = ""
    due: str = ""
    subject_type: str = ""
    subject_id: str = ""
    subject_title: str = ""
    subject_href: str = ""
    proposer: str = ""
    confidence: float = 0.0
    evidence_count: int = 0
    trusted_source: bool = False


@dataclass(frozen=True, slots=True)
class PolicyResult:
    review_id: str
    outcome: str
    explanation: str
    policy_version: str = POLICY_VERSION
    replayed: bool = False
    dry_run: bool = True
