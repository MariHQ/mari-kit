"""Trust, authority, scope, and retention policy primitives."""

from __future__ import annotations

import datetime as dt
import fnmatch
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class TrustLevel(StrEnum):
    UNTRUSTED = "untrusted"
    INTERNAL = "internal"
    PRIVILEGED = "privileged"
    SYSTEM = "system"


class WriteChannel(StrEnum):
    USER = "user"
    MODEL = "model"
    TOOL_RESULT = "tool_result"
    EXTERNAL_DOCUMENT = "external_document"
    IMPORT = "import"
    HUMAN_REVIEW = "human_review"


class ContentInterpretation(StrEnum):
    DATA = "data"
    FACT = "fact"
    PROCEDURE = "procedure"
    INSTRUCTION = "instruction"


class WriteDisposition(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    QUARANTINE = "quarantine"


@dataclass(frozen=True, slots=True, kw_only=True)
class MemoryWrite:
    write_id: str
    content: str
    channel: WriteChannel
    trust: TrustLevel
    interpretation: ContentInterpretation
    requested_scope: str
    source_ids: tuple[str, ...]
    taints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.write_id.strip() or not self.content.strip() or not self.requested_scope.strip():
            raise ValueError("write ID, content, and requested scope are required")
        object.__setattr__(self, "source_ids", tuple(dict.fromkeys(self.source_ids)))
        object.__setattr__(self, "taints", tuple(sorted(set(self.taints))))


@dataclass(frozen=True, slots=True, kw_only=True)
class WriteDecision:
    disposition: WriteDisposition
    reasons: tuple[str, ...]
    inherited_taints: tuple[str, ...]


def evaluate_write(write: MemoryWrite) -> WriteDecision:
    """Apply conservative deterministic write-boundary rules."""

    if not write.source_ids:
        return WriteDecision(disposition=WriteDisposition.REJECT, reasons=("missing_provenance",), inherited_taints=write.taints)
    dangerous = {"secret", "external_instruction", "privilege_amplification"} & set(write.taints)
    untrusted_behavior = write.trust is TrustLevel.UNTRUSTED and write.interpretation in {
        ContentInterpretation.PROCEDURE,
        ContentInterpretation.INSTRUCTION,
    }
    reasons = tuple(sorted(dangerous | ({"untrusted_behavior"} if untrusted_behavior else set())))
    if reasons:
        return WriteDecision(disposition=WriteDisposition.QUARANTINE, reasons=reasons, inherited_taints=write.taints)
    return WriteDecision(disposition=WriteDisposition.ACCEPT, reasons=(), inherited_taints=write.taints)


def inherit_taints(writes: Iterable[MemoryWrite]) -> tuple[str, ...]:
    return tuple(sorted({taint for write in writes for taint in write.taints}))


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceAssertion:
    assertion_id: str
    predicate: str
    value: Any
    source_kind: str
    confidence: float = 1.0
    independence: float = 1.0
    valid_from: dt.datetime | None = None
    valid_to: dt.datetime | None = None

    def __post_init__(self) -> None:
        if not self.assertion_id or not self.predicate or not self.source_kind:
            raise ValueError("assertion identity, predicate, and source kind are required")
        for name, value in (("confidence", self.confidence), ("independence", self.independence)):
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.valid_from is not None and self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("assertion valid-time interval is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthorityPolicy:
    source_weights: Mapping[str, float] = field(default_factory=dict)
    corroboration_weight: float = 0.15
    minimum_margin: float = 0.1

    def __post_init__(self) -> None:
        values = dict(self.source_weights)
        if any(not math.isfinite(value) or not 0 <= value <= 1 for value in values.values()):
            raise ValueError("source weights must be in [0, 1]")
        if self.corroboration_weight < 0 or self.minimum_margin < 0:
            raise ValueError("authority weights and margins must not be negative")
        object.__setattr__(self, "source_weights", MappingProxyType(values))


@dataclass(frozen=True, slots=True, kw_only=True)
class AssertionResolution:
    selected: SourceAssertion | None
    alternatives: tuple[SourceAssertion, ...]
    scores: tuple[tuple[str, float], ...]
    disputed: bool


def resolve_assertions(
    assertions: Iterable[SourceAssertion], *, policy: AuthorityPolicy, at_time: dt.datetime | None = None
) -> AssertionResolution:
    values = tuple(
        value
        for value in assertions
        if at_time is None
        or (value.valid_from is None or value.valid_from <= at_time)
        and (value.valid_to is None or at_time < value.valid_to)
    )
    if not values:
        return AssertionResolution(selected=None, alternatives=(), scores=(), disputed=True)
    predicates = {value.predicate for value in values}
    if len(predicates) != 1:
        raise ValueError("assertions must concern one predicate")
    grouped: dict[str, list[SourceAssertion]] = {}
    for assertion in values:
        grouped.setdefault(repr(assertion.value), []).append(assertion)
    scored: list[tuple[float, str, SourceAssertion]] = []
    for key, group in grouped.items():
        base = sum(
            policy.source_weights.get(item.source_kind, 0.5) * item.confidence * item.independence
            for item in group
        )
        score = base + policy.corroboration_weight * max(0, len({item.source_kind for item in group}) - 1)
        representative = sorted(group, key=lambda item: item.assertion_id)[0]
        scored.append((score, key, representative))
    scored.sort(key=lambda item: (-item[0], item[1]))
    margin = scored[0][0] - scored[1][0] if len(scored) > 1 else scored[0][0]
    disputed = len(scored) > 1 and margin < policy.minimum_margin
    selected = None if disputed else scored[0][2]
    return AssertionResolution(
        selected=selected,
        alternatives=tuple(item for item in values if selected is None or item.assertion_id != selected.assertion_id),
        scores=tuple((item[2].assertion_id, item[0]) for item in scored),
        disputed=disputed,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class ScopeGrant:
    principal: str
    read: tuple[str, ...] = ()
    write: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class ScopePolicy:
    grants: tuple[ScopeGrant, ...]

    def allows(self, principal: str, action: str, scope: str) -> bool:
        if action not in {"read", "write"}:
            raise ValueError("action must be read or write")
        return any(
            grant.principal == principal
            and any(fnmatch.fnmatchcase(scope, pattern) for pattern in getattr(grant, action))
            for grant in self.grants
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class PromotionProposal:
    artifact_id: str
    source_scope: str
    target_scope: str
    principal: str
    allowed: bool
    reason: str


def propose_promotion(
    *, artifact_id: str, source_scope: str, target_scope: str, principal: str, policy: ScopePolicy
) -> PromotionProposal:
    readable = policy.allows(principal, "read", source_scope)
    writable = policy.allows(principal, "write", target_scope)
    allowed = readable and writable
    reason = "allowed" if allowed else "source_not_readable" if not readable else "target_not_writable"
    return PromotionProposal(artifact_id=artifact_id, source_scope=source_scope, target_scope=target_scope, principal=principal, allowed=allowed, reason=reason)


@dataclass(frozen=True, slots=True, kw_only=True)
class RetentionRecord:
    record_id: str
    created_at: dt.datetime
    expires_at: dt.datetime | None = None
    purposes: tuple[str, ...] = ()
    legal_hold: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class RetentionPolicy:
    default_ttl_days: int | None = None
    allowed_purposes: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.default_ttl_days is not None and self.default_ttl_days < 0:
            raise ValueError("default TTL must not be negative")
        object.__setattr__(self, "allowed_purposes", MappingProxyType(dict(self.allowed_purposes)))


class RetentionActionKind(StrEnum):
    DELETE = "delete"
    INVALIDATE = "invalidate"
    HOLD = "hold"


@dataclass(frozen=True, slots=True, kw_only=True)
class RetentionAction:
    record_id: str
    kind: RetentionActionKind
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RetentionPlan:
    actions: tuple[RetentionAction, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class PurposeDecision:
    allowed: bool
    reason: str


def evaluate_purpose(record: RetentionRecord, *, requested_purpose: str) -> PurposeDecision:
    if not requested_purpose.strip():
        raise ValueError("requested purpose is required")
    if record.purposes and requested_purpose not in record.purposes:
        return PurposeDecision(allowed=False, reason="purpose_mismatch")
    return PurposeDecision(allowed=True, reason="allowed")


def plan_retention(
    *, records: Iterable[RetentionRecord], dependencies: Mapping[str, Iterable[str]], now: dt.datetime, policy: RetentionPolicy
) -> RetentionPlan:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    values = {record.record_id: record for record in records}
    expired: set[str] = set()
    held: set[str] = set()
    for record in values.values():
        expiry = record.expires_at
        if expiry is None and policy.default_ttl_days is not None:
            expiry = record.created_at + dt.timedelta(days=policy.default_ttl_days)
        if expiry is not None and expiry <= now:
            (held if record.legal_hold else expired).add(record.record_id)
    invalidated: set[str] = set()
    queue = list(expired)
    while queue:
        parent = queue.pop()
        for child in dependencies.get(parent, ()):
            if child not in expired and child not in invalidated:
                invalidated.add(child)
                queue.append(child)
    actions = [RetentionAction(record_id=item, kind=RetentionActionKind.DELETE, reason="expired") for item in sorted(expired)]
    actions += [RetentionAction(record_id=item, kind=RetentionActionKind.INVALIDATE, reason="dependency_deleted") for item in sorted(invalidated)]
    actions += [RetentionAction(record_id=item, kind=RetentionActionKind.HOLD, reason="legal_hold") for item in sorted(held)]
    return RetentionPlan(actions=tuple(actions))
