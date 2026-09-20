"""Behavioral tests for the incident-response company brain example."""

from __future__ import annotations

import json

import pytest

from examples.company_brains.incident import (
    CUSTOMER_COMMS,
    INCIDENT_THREAD_V1,
    INCIDENT_THREAD_V2,
    RUNBOOK_V1,
    RUNBOOK_V2,
    build_answers,
    grounded_answer,
    plan_invalidation,
    run,
)
from mari_kit.errors import MalformedModelOutput
from mari_kit.knowledge import KnowledgeDependency, section_revisions


def test_run_result_is_json_serializable():
    result = run()
    decoded = json.loads(json.dumps(result))
    assert decoded["scenario"] == result["scenario"]
    assert decoded["invalidated"] == list(result["invalidated"])
    assert decoded["preserved"] == list(result["preserved"])
    assert decoded["changed_sections"] == list(result["changed_sections"])
    assert decoded["removed_sources"] == list(result["removed_sources"])
    assert set(decoded["impacts"]) == set(result["impacts"])
    assert set(decoded["tracked_artifacts"]) == set(result["tracked_artifacts"])


def test_changed_runbook_section_invalidates_only_its_dependents():
    result = run()
    assert result["invalidated"] == (
        "answer:checkout-mitigation",
        "answer:customer-status-update",
        "digest:checkout-runbook",
    )
    mitigation = result["impacts"]["answer:checkout-mitigation"]
    assert mitigation["status"] == "stale"
    runbook_changes = [
        change
        for change in mitigation["changes"]
        if change["section_id"].startswith("checkout-incident-runbook/")
    ]
    assert [change["section_id"] for change in runbook_changes] == [
        "checkout-incident-runbook/mitigation"
    ]
    assert (
        runbook_changes[0]["expected_revision"]
        != runbook_changes[0]["current_revision"]
    )


def test_whole_document_digest_is_conservatively_invalidated():
    result = run()
    digest = result["impacts"]["digest:checkout-runbook"]
    assert digest["status"] == "stale"
    assert len(digest["changes"]) == 1
    change = digest["changes"][0]
    assert change["section_id"] == ""
    assert change["expected_revision"] == RUNBOOK_V1.revision
    assert change["current_revision"] == RUNBOOK_V2.revision


def test_removed_source_invalidates_its_artifacts_as_missing():
    result = run()
    assert result["removed_sources"] == (CUSTOMER_COMMS.document_id,)
    report = result["impacts"]["answer:customer-status-update"]
    assert report["status"] == "missing"
    assert report["reusable"] is False
    assert report["missing_dependency_ids"] == [CUSTOMER_COMMS.document_id]
    assert report["changes"] == []


def test_unaffected_guidance_is_preserved_by_section_revision():
    result = run()
    assert result["preserved"] == (
        "answer:checkout-detection",
        "answer:checkout-escalation",
    )
    assert "answer:checkout-escalation" not in result["invalidated"]
    guidance = result["unaffected_guidance"]
    current = section_revisions((RUNBOOK_V2,))
    key = (RUNBOOK_V2.document_id, guidance["section_id"])
    assert guidance["section_revision"] == current[key]

    escalation = build_answers()["answer:checkout-escalation"]
    assert guidance["answer"] == escalation.answer


def test_section_change_is_distinguished_from_containing_document_change():
    result = run()
    assert result["changed_sections"] == (
        f"{RUNBOOK_V2.document_id}#checkout-incident-runbook/mitigation",
        f"{INCIDENT_THREAD_V2.document_id}#root",
    )
    assert RUNBOOK_V1.document_id not in result["changed_sections"]


def test_plan_invalidation_reports_removed_section_without_document_change():
    dependency = KnowledgeDependency(
        document_id=RUNBOOK_V1.document_id,
        revision=RUNBOOK_V1.revision,
        section_id="checkout-incident-runbook/retired",
        section_revision="retired-section-revision",
    )
    plan = plan_invalidation(
        {"answer:retired": (dependency,)},
        {RUNBOOK_V2.document_id: RUNBOOK_V2.revision},
        current_section_revisions=section_revisions((RUNBOOK_V2,)),
    )
    assert plan["invalidated"] == ("answer:retired",)
    assert plan["impacts"]["answer:retired"]["status"] == "missing"
    assert plan["impacts"]["answer:retired"]["missing_dependency_ids"] == [
        dependency.dependency_id
    ]
    assert plan["removed_sources"] == ()


def test_plan_invalidation_preserves_unchanged_section_after_document_edit():
    escalation = build_answers()["answer:checkout-escalation"]
    plan = plan_invalidation(
        {"answer:checkout-escalation": escalation.knowledge_dependencies},
        {RUNBOOK_V2.document_id: RUNBOOK_V2.revision},
        current_section_revisions=section_revisions((RUNBOOK_V2,)),
    )
    assert plan["invalidated"] == ()
    assert plan["preserved"] == ("answer:checkout-escalation",)


def test_grounded_answer_binds_exact_section_dependency():
    answer = build_answers()["answer:checkout-escalation"]
    dependency = answer.knowledge_dependencies[0]
    assert dependency.document_id == RUNBOOK_V1.document_id
    assert dependency.section_id == "checkout-incident-runbook/escalation"
    assert dependency.section_revision


def test_grounded_answer_rejects_quote_absent_from_revision():
    with pytest.raises(MalformedModelOutput, match="not present in the document"):
        grounded_answer(
            "How do we detect checkout incidents?",
            (RUNBOOK_V1, INCIDENT_THREAD_V1),
            "Fabricated guidance.",
            [
                {
                    "document_id": RUNBOOK_V1.document_id,
                    "quote": "This sentence is absent.",
                }
            ],
        )


def test_grounded_answer_rejects_unknown_document():
    with pytest.raises(MalformedModelOutput, match="unknown document"):
        grounded_answer(
            "How do we mitigate checkout errors?",
            (RUNBOOK_V1, INCIDENT_THREAD_V1),
            "Grounded in an unknown source.",
            [{"document_id": "github:acme/operations/unknown.md", "quote": "anything"}],
        )


def test_grounded_answer_rejects_grounded_answer_without_evidence():
    from mari_kit.knowledge import parse_answer

    with pytest.raises(MalformedModelOutput, match="requires evidence"):
        parse_answer(
            "How do we detect checkout incidents?",
            (RUNBOOK_V1,),
            {"answer": "Checkout is fine.", "evidence": [], "disposition": "grounded"},
        )


def test_knowledge_dependency_requires_section_id_and_revision_together():
    with pytest.raises(ValueError, match="must be supplied together"):
        KnowledgeDependency(
            document_id=RUNBOOK_V1.document_id,
            revision=RUNBOOK_V1.revision,
            section_id="checkout-incident-runbook/mitigation",
        )
