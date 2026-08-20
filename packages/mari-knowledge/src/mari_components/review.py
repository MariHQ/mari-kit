"""Unified Review filtering and deterministic approval use cases."""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, replace

from mari_components.knowledge.approvals import (
    ApprovalPolicy,
    ReviewItem,
    evaluate_approval,
)

from mari_components.review_types import POLICY_VERSION, PolicyResult, ReviewRecord


@dataclass(frozen=True, slots=True)
class ReviewPorts:
    existing_decision: Callable[[str, str, str], tuple[str, str] | None]
    record_decision: Callable[[ReviewRecord, PolicyResult, str, str], None]
    apply_approval: Callable[[ReviewRecord], None]
    audit_decision: Callable[[ReviewRecord, PolicyResult, str], None]


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(max(offset, 0)).encode()).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        raw = cursor + "=" * (-len(cursor) % 4)
        return max(0, int(base64.urlsafe_b64decode(raw).decode()))
    except (ValueError, UnicodeDecodeError):
        raise ValueError("Invalid Review cursor") from None


def filter_items(
    items: Iterable[ReviewRecord], *, kinds: list[str] | None = None,
    statuses: list[str] | None = None, sources: list[str] | None = None,
    assignees: list[str] | None = None, due: str | None = None,
) -> list[ReviewRecord]:
    selected = [set(values or []) for values in (kinds, statuses, sources, assignees)]
    due_filter = (due or "").lower()
    today = dt.date.today().isoformat()
    result = []
    for item in items:
        if selected[0] and item.kind not in selected[0]:
            continue
        if selected[1] and item.status not in selected[1]:
            continue
        if selected[2] and item.source not in selected[2]:
            continue
        if selected[3] and item.assignee not in selected[3]:
            continue
        if due_filter == "overdue" and (not item.due or item.due >= today):
            continue
        if due_filter == "dated" and not item.due:
            continue
        if due_filter == "undated" and item.due:
            continue
        result.append(item)
    return sorted(result, key=lambda item: (
        item.status != "pending", item.due or "9999-12-31", item.kind, item.id,
    ))


def evaluate_policy(
    item: ReviewRecord, reviewer: str, *, min_confidence: float = .9,
    min_evidence: int = 2,
) -> PolicyResult:
    decision = evaluate_approval(
        ReviewItem(
            item.id, item.kind, item.proposer.casefold(), item.confidence,
            item.evidence_count, item.trusted_source,
        ),
        reviewer.casefold(),
        ApprovalPolicy(
            minimum_confidence=min_confidence,
            minimum_evidence=min_evidence,
            version=POLICY_VERSION,
        ),
    )
    return PolicyResult(
        item.id, decision.outcome, decision.explanation,
        policy_version=decision.policy_version,
    )


def decide(
    item: ReviewRecord,
    reviewer: str,
    ports: ReviewPorts,
    *,
    dry_run: bool = True,
    permission: Callable[[str, ReviewRecord], bool] = lambda _actor, _item: True,
) -> PolicyResult:
    if not permission(reviewer, item):
        return PolicyResult(
            item.id, "deny", "Reviewer lacks permission for this item.", dry_run=dry_run,
        )
    result = replace(evaluate_policy(item, reviewer), dry_run=dry_run)
    if dry_run:
        return result
    fingerprint = hashlib.sha256(
        json.dumps(asdict(item), sort_keys=True).encode(),
    ).hexdigest()
    existing = ports.existing_decision(item.id, POLICY_VERSION, fingerprint)
    if existing:
        return PolicyResult(
            item.id, existing[0], existing[1], replayed=True, dry_run=False,
        )
    ports.record_decision(item, result, reviewer, fingerprint)
    if result.outcome == "allow":
        ports.apply_approval(item)
    ports.audit_decision(item, result, reviewer)
    return result
