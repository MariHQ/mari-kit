from __future__ import annotations

import datetime as dt

import pytest

from mari_components.knowledge import (
    Activity,
    AdmissionDisposition,
    AdmissionSignals,
    ConsolidationBudget,
    KnowledgeArtifact,
    KnowledgeScope,
    PromotionSignal,
    admit_candidate,
    plan_consolidation,
)


def test_admission_quarantine_precedes_confidence() -> None:
    decision = admit_candidate(
        AdmissionSignals(
            confidence=1.0,
            has_provenance=True,
            evidence_span_valid=True,
            source_authorized=True,
            contains_external_instruction=True,
        )
    )

    assert decision.disposition is AdmissionDisposition.QUARANTINE
    assert decision.reasons == ("external_instruction",)


def test_admission_rejects_recalled_content_as_new_evidence() -> None:
    decision = admit_candidate(
        AdmissionSignals(
            confidence=0.99,
            has_provenance=True,
            evidence_span_valid=True,
            source_authorized=True,
            recalled_input=True,
        )
    )

    assert decision.disposition is AdmissionDisposition.REJECT
    assert "recalled_input" in decision.reasons


def test_consolidation_is_budgeted_and_deterministic() -> None:
    plan = plan_consolidation(
        [
            PromotionSignal(
                artifact_id="useful",
                recurrence=0.8,
                recency=0.8,
                usefulness=1,
                evidence_diversity=1,
                estimated_calls=1,
                estimated_tokens=80,
            ),
            PromotionSignal(
                artifact_id="weak",
                recurrence=0.2,
                recency=0.2,
                usefulness=0.2,
                evidence_diversity=0.2,
                estimated_calls=1,
                estimated_tokens=30,
            ),
        ],
        budget=ConsolidationBudget(max_model_calls=1, max_tokens=100),
        minimum_score=0.3,
    )

    assert plan.selected_ids == ("useful",)
    assert plan.deferred_ids == ("weak",)


def test_artifact_revisions_require_temporal_integrity() -> None:
    activity = Activity(identifier="extract/v1", implementation="rules")
    artifact = KnowledgeArtifact(
        artifact_id="fact:1",
        revision="sha256:abc",
        value={"claim": "x"},
        scope=KnowledgeScope(tenant="acme"),
        recorded_at=dt.datetime.now(dt.UTC),
        generated_by=activity,
    )
    assert artifact.scope.tenant == "acme"

    with pytest.raises(ValueError, match="timezone-aware"):
        KnowledgeArtifact(
            artifact_id="fact:1",
            revision="sha256:def",
            value={},
            scope=KnowledgeScope(tenant="acme"),
            recorded_at=dt.datetime.now(),
            generated_by=activity,
        )
