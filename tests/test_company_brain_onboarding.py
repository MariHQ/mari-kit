"""Behavioral tests for the onboarding company-brain example."""

from __future__ import annotations

import json

import pytest

from examples.company_brains import onboarding
from mari_kit import Evidence, KnowledgeDocument, Principal
from mari_kit.errors import MalformedModelOutput
from mari_kit.knowledge import (
    AnswerDisposition,
    FreshnessStatus,
    assess_freshness,
    deduplicate_fact_candidates,
    parse_answer,
    parse_claim_assessments,
    parse_facts,
    parse_refinement,
    section_revisions,
)

_ENGINEER = Principal(kind="team", identifier="engineering")
_PEOPLE_OPS = Principal(kind="team", identifier="people-ops")


def test_run_is_credential_free_and_json_serializable():
    first = onboarding.run()
    assert isinstance(first, dict)
    encoded = json.dumps(first)
    assert json.loads(encoded)["handbook_fact_claims"]
    assert onboarding.run() == first


def test_facts_are_bound_to_exact_sections():
    facts = onboarding.handbook_facts()
    assert tuple(fact.evidence[0].section_id for fact in facts) == (
        "welcome",
        "equipment",
        "security-training",
    )
    for fact in facts:
        evidence = fact.evidence[0]
        assert evidence.revision == onboarding.HANDBOOK_V1.revision
        assert evidence.section_revision
        assert (
            onboarding.HANDBOOK_V1.body[evidence.start : evidence.end] == evidence.quote
        )


def test_policy_edit_invalidates_only_the_edited_section():
    result = onboarding.run()
    assert result["changed_sections"] == ("handbook/onboarding#equipment",)
    assert result["section_status_after_edit"] == {
        "welcome": "current",
        "equipment": "stale",
        "security-training": "current",
    }
    assert result["document_level_fallback_status"] == FreshnessStatus.STALE.value


def test_unchanged_sections_are_reused_and_only_edited_section_is_pending():
    result = onboarding.run()
    assert result["pending_sections_after_edit"] == ("handbook/onboarding#equipment",)
    reused = result["reused_unchanged_section_facts"]
    assert reused == (
        "New hires complete onboarding within their first two weeks.",
        "All employees complete security training every year.",
    )
    assert all("equipment" not in claim.casefold() for claim in reused)
    assert result["duplicate_reuse_count"] == 0


def test_unknown_document_and_invented_quote_fail_closed():
    with pytest.raises(MalformedModelOutput):
        parse_facts(
            (onboarding.HANDBOOK_V1,),
            {
                "facts": [
                    {
                        "claim": "Unverifiable.",
                        "evidence": [
                            {
                                "document_id": "handbook/missing",
                                "quote": "Unverifiable.",
                            }
                        ],
                    }
                ]
            },
        )
    with pytest.raises(MalformedModelOutput):
        parse_facts(
            (onboarding.HANDBOOK_V1,),
            {
                "facts": [
                    {
                        "claim": "Security training is monthly.",
                        "evidence": [
                            {
                                "document_id": onboarding.HANDBOOK_V1.document_id,
                                "quote": "Security training is monthly.",
                            }
                        ],
                    }
                ]
            },
        )


def test_unverifiable_assessment_quote_downgrades_to_uncertain():
    assessment = parse_claim_assessments(
        ("All employees complete security training every year.",),
        (onboarding.HANDBOOK_V1,),
        {
            "assessments": [
                {
                    "claim": "All employees complete security training every year.",
                    "verdict": "supported",
                    "explanation": "Quoted.",
                    "evidence": [
                        {
                            "document_id": onboarding.HANDBOOK_V1.document_id,
                            "quote": "All employees complete security training monthly.",
                        }
                    ],
                }
            ]
        },
    )[0]
    assert assessment.verdict == "uncertain"
    assert assessment.evidence == ()
    assert "could not be verified" in assessment.explanation


def test_answer_without_evidence_is_an_explicit_abstention():
    answer = parse_answer(
        "What is the annual travel stipend?",
        onboarding.DOCUMENTS,
        {
            "answer": "The onboarding knowledge does not state a stipend.",
            "disposition": "insufficient_evidence",
            "evidence": [],
        },
    )
    assert answer.disposition is AnswerDisposition.INSUFFICIENT_EVIDENCE
    assert answer.grounding_coverage == 0


def test_missing_source_and_removed_section_report_missing():
    removed = KnowledgeDocument(
        source_id=onboarding.HANDBOOK_V1.source_id,
        external_id=onboarding.HANDBOOK_V1.external_id,
        title=onboarding.HANDBOOK_V1.title,
        body="# Welcome\nNew hires complete onboarding within their first two weeks.\n",
        revision="handbook-v3",
    )
    revised = onboarding.handbook_after_edit()
    facts = onboarding.handbook_facts()
    equipment = next(
        fact for fact in facts if fact.evidence[0].section_id == "equipment"
    )
    current_revisions = {
        revised.document_id: revised.revision,
        onboarding.IT_GUIDE.document_id: onboarding.IT_GUIDE.revision,
        onboarding.HR_POLICY.document_id: onboarding.HR_POLICY.revision,
    }
    missing_source = assess_freshness(
        (
            Evidence(
                document_id="handbook/retired-benefits",
                revision="v1",
                quote="Retired benefit.",
            ),
        ),
        current_revisions,
    )
    assert missing_source.status is FreshnessStatus.MISSING
    assert not missing_source.reusable
    assert missing_source.missing_dependency_ids == ("handbook/retired-benefits",)

    removed_section = assess_freshness(
        equipment.evidence,
        {removed.document_id: removed.revision},
        current_section_revisions=section_revisions((removed,)),
    )
    assert removed_section.status is FreshnessStatus.MISSING
    assert removed_section.missing_dependency_ids == (
        f"{removed.document_id}#equipment",
    )


def test_repeated_extraction_reuses_existing_claims():
    facts = onboarding.handbook_facts()
    assert (
        deduplicate_fact_candidates(
            facts, existing_claims=[fact.claim for fact in facts]
        )
        == ()
    )


def test_policy_edit_proposal_requires_an_exact_source_substring():
    edit = onboarding.proposed_policy_edit()[0]
    revised = onboarding.handbook_after_edit()
    assert edit.original in onboarding.HANDBOOK_V1.body
    assert edit.replacement in revised.body
    unchanged = (
        onboarding.HANDBOOK_V1.body.replace(edit.original, "").strip()
        == revised.body.replace(edit.replacement, "").strip()
    )
    assert unchanged
    with pytest.raises(MalformedModelOutput):
        parse_refinement(
            onboarding.HANDBOOK_V1,
            {
                "edits": [
                    {
                        "original": "This sentence was never in the policy.",
                        "replacement": "Anything.",
                        "reason": "Invalid source.",
                    }
                ]
            },
        )


def test_restricted_hr_document_is_hidden_from_employee_retrieval():
    employee_allowed = onboarding.host_allowed_document_ids((_ENGINEER,))
    people_ops_allowed = onboarding.host_allowed_document_ids((_PEOPLE_OPS,))
    assert onboarding.HR_POLICY.document_id not in employee_allowed
    assert onboarding.HR_POLICY.document_id in people_ops_allowed
    assert onboarding.HANDBOOK_V1.document_id in employee_allowed

    result = onboarding.run()
    assert result["restricted_hr_hidden_from_employee"]
    assert onboarding.HR_POLICY.document_id not in result["employee_retrieval_hits"]
    assert onboarding.HR_POLICY.document_id in result["people_ops_retrieval_hits"]
    assert result["employee_served_hr_facts"] is False


def test_host_serves_hr_facts_only_to_an_authorized_principal():
    hr = onboarding.hr_facts()
    employee_allowed = onboarding.host_allowed_document_ids((_ENGINEER,))
    people_ops_allowed = onboarding.host_allowed_document_ids((_PEOPLE_OPS,))
    assert onboarding.serve_facts(hr, employee_allowed) == ()
    served = onboarding.serve_facts(hr, people_ops_allowed)
    assert len(served) == 1
    assert served[0].evidence[0].document_id == onboarding.HR_POLICY.document_id
