"""Evidence and safety admission before memory reconciliation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


class AdmissionDisposition(StrEnum):
    ACCEPT = "accept"
    DEFER = "defer"
    REJECT = "reject"
    QUARANTINE = "quarantine"


@dataclass(frozen=True, slots=True, kw_only=True)
class AdmissionSignals:
    confidence: float
    has_provenance: bool
    evidence_span_valid: bool
    source_authorized: bool
    recalled_input: bool = False
    contains_secret: bool = False
    contains_external_instruction: bool = False

    def __post_init__(self) -> None:
        if not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be a finite value in [0, 1]")


@dataclass(frozen=True, slots=True, kw_only=True)
class AdmissionThresholds:
    accept: float = 0.9
    defer: float = 0.65

    def __post_init__(self) -> None:
        if not 0 <= self.defer <= self.accept <= 1:
            raise ValueError("thresholds must satisfy 0 <= defer <= accept <= 1")


@dataclass(frozen=True, slots=True, kw_only=True)
class AdmissionDecision:
    disposition: AdmissionDisposition
    reasons: tuple[str, ...]


def admit_candidate(
    signals: AdmissionSignals,
    *,
    thresholds: AdmissionThresholds | None = None,
) -> AdmissionDecision:
    """Apply conservative disposition precedence without persisting anything."""

    selected = thresholds or AdmissionThresholds()
    quarantine = tuple(
        reason
        for present, reason in (
            (signals.contains_secret, "contains_secret"),
            (signals.contains_external_instruction, "external_instruction"),
        )
        if present
    )
    if quarantine:
        return AdmissionDecision(
            disposition=AdmissionDisposition.QUARANTINE, reasons=quarantine
        )
    rejection = tuple(
        reason
        for failed, reason in (
            (not signals.has_provenance, "missing_provenance"),
            (not signals.evidence_span_valid, "invalid_evidence_span"),
            (not signals.source_authorized, "unauthorized_source"),
            (signals.recalled_input, "recalled_input"),
        )
        if failed
    )
    if rejection:
        return AdmissionDecision(
            disposition=AdmissionDisposition.REJECT, reasons=rejection
        )
    if signals.confidence >= selected.accept:
        return AdmissionDecision(disposition=AdmissionDisposition.ACCEPT, reasons=())
    if signals.confidence >= selected.defer:
        return AdmissionDecision(
            disposition=AdmissionDisposition.DEFER,
            reasons=("confidence_review_band",),
        )
    return AdmissionDecision(
        disposition=AdmissionDisposition.REJECT,
        reasons=("confidence_below_defer",),
    )
