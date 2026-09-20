"""Behavioral tests for the company decision memory brain example.

Covers the happy path, the explicit review policy, and the failure paths the
brain must surface rather than hide: fabricated citations, missing provenance,
untrusted instruction-bearing sources, and stale evidence after source edits.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from examples.company_brains import decisions as brain
from mari_kit import DecisionCandidate, KnowledgeDocument, MalformedModelOutput
from mari_kit.knowledge import parse_decisions


def _run() -> dict[str, Any]:
    return cast("dict[str, Any]", brain.run())


def _as_dict(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    return cast("dict[str, Any]", value)


def _decision_row(result: dict[str, Any], decision_id: str) -> dict[str, Any]:
    rows = result["decisions"]
    return cast(
        "dict[str, Any]",
        next(row for row in rows if row["decision_id"] == decision_id),
    )


def _candidate(
    statement: str, quote: str, *, document: KnowledgeDocument
) -> DecisionCandidate:
    return parse_decisions(
        (document,),
        {
            "decisions": [
                {
                    "statement": statement,
                    "evidence": [{"document_id": document.document_id, "quote": quote}],
                }
            ]
        },
    )[0]


def test_run_is_json_serializable_and_passes_checks() -> None:
    result = _run()
    assert result["passed"] is True
    round_tripped = json.loads(json.dumps(result))
    assert round_tripped["checks"] == result["checks"]
    assert set(result) >= {
        "scope",
        "review_policy",
        "decisions",
        "invalid_citations",
        "provenance_validation",
        "governance",
        "revised_evidence",
        "checks",
        "passed",
    }


def test_approved_decisions_bind_exact_revision_and_section() -> None:
    result = _run()
    approved = {
        row["decision_id"]
        for row in result["decisions"]
        if row["review_state"] == "approved"
    }
    assert approved == {"decision:retention", "decision:deployment"}
    for decision_id in approved:
        row = _decision_row(result, decision_id)
        assert row["freshness"] == "current"
        assert row["write_disposition"] == "accept"
        assert len(row["evidence"]) == 1
        evidence = row["evidence"][0]
        assert evidence["revision"] == "d1"
        assert evidence["section_id"]
        assert evidence["section_revision"]
        assert evidence["quote"]


def test_grounding_score_comes_from_the_library_not_the_host() -> None:
    result = _run()
    retention = _decision_row(result, "decision:retention")
    assert retention["grounding_coverage"] == pytest.approx(0.9)
    access = _decision_row(result, "decision:access-approval")
    assert access["grounding_coverage"] < brain.DEFAULT_POLICY.minimum_grounding


def test_low_grounding_decision_is_rejected() -> None:
    result = _run()
    row = _decision_row(result, "decision:access-approval")
    assert row["review_state"] == "rejected"
    assert "below_minimum_grounding" in row["reasons"]


def test_untrusted_instruction_source_is_quarantined_not_approved() -> None:
    result = _run()
    row = _decision_row(result, "decision:vendor-access")
    assert row["write_disposition"] == "quarantine"
    assert row["review_state"] == "proposed"
    assert "quarantined_provenance" in row["reasons"]


def test_missing_provenance_is_rejected_by_governance() -> None:
    result = _run()
    governance = _as_dict(result["governance"])
    assert governance["missing_provenance_disposition"] == "reject"
    assert governance["missing_provenance_reasons"] == ("missing_provenance",)


def test_review_policy_treats_stale_evidence_as_proposed() -> None:
    candidate = _candidate(
        "Customer data retention is thirty days.",
        "Customer data retention is thirty days.",
        document=brain.DECISION_LOG_V1,
    )
    write = brain._write_for(candidate, decision_id="decision:x", scope=brain.SCOPE)
    fresh = brain._review(
        candidate,
        decision_id="decision:x",
        freshness_status="current",
        freshness_reusable=True,
        write=write,
        policy=brain.DEFAULT_POLICY,
    )
    stale = brain._review(
        candidate,
        decision_id="decision:x",
        freshness_status="stale",
        freshness_reusable=False,
        write=write,
        policy=brain.DEFAULT_POLICY,
    )
    assert fresh["review_state"] == "approved"
    assert stale["review_state"] == "proposed"
    assert stale["reasons"] == ("evidence_stale",)


def test_unknown_document_citation_is_rejected() -> None:
    with pytest.raises(MalformedModelOutput, match="unknown document"):
        parse_decisions(
            (brain.DECISION_LOG_V1, brain.SECURITY_POLICY),
            {
                "decisions": [
                    {
                        "statement": "Retention exists.",
                        "evidence": [
                            {
                                "document_id": "handbook/ghost",
                                "quote": "Customer data retention is thirty days.",
                            }
                        ],
                    }
                ]
            },
        )


def test_quote_not_present_in_document_is_rejected() -> None:
    with pytest.raises(MalformedModelOutput, match="not present"):
        parse_decisions(
            (brain.DECISION_LOG_V1,),
            {
                "decisions": [
                    {
                        "statement": "Retention exists.",
                        "evidence": [
                            {
                                "document_id": brain.DECISION_LOG_V1.document_id,
                                "quote": "Customer data retention is forty five days.",
                            }
                        ],
                    }
                ]
            },
        )


@pytest.mark.parametrize(
    ("output", "message"),
    [
        ({"decisions": [{"statement": "Retention exists."}]}, "non-empty array"),
        (
            {
                "decisions": [
                    {
                        "evidence": [
                            {
                                "document_id": brain.DECISION_LOG_V1.document_id,
                                "quote": "Customer data retention is thirty days.",
                            }
                        ]
                    }
                ]
            },
            "statement is required",
        ),
        ({"decisions": {"statement": "Retention exists."}}, "JSON array"),
    ],
)
def test_malformed_decision_outputs_are_rejected(output: object, message: str) -> None:
    with pytest.raises(MalformedModelOutput, match=message):
        parse_decisions((brain.DECISION_LOG_V1,), output)


def test_all_invalid_citation_probes_report_rejection() -> None:
    result = _run()
    invalid = _as_dict(result["invalid_citations"])
    probes = invalid["probes"]
    assert invalid["all_rejected"] is True
    assert all(probe["rejected"] for probe in probes)
    assert all(probe["error_type"] == "MalformedModelOutput" for probe in probes)


def test_provenance_validation_detects_stale_and_tampered_citations() -> None:
    report = _as_dict(_run()["provenance_validation"])
    accepted_current = _as_dict(report["accepted_current"])
    unknown_revision = _as_dict(report["unknown_revision"])
    not_visible_revision = _as_dict(report["not_visible_revision"])
    tampered_quote = _as_dict(report["tampered_quote"])
    assert accepted_current["accepted"] is True
    assert unknown_revision["issue_kinds"] == ("unresolved",)
    assert not_visible_revision["issue_kinds"] == ("not_visible",)
    assert tampered_quote["issue_kinds"] == ("quote_mismatch",)


def test_revised_evidence_marks_only_the_changed_section_stale() -> None:
    revised = _as_dict(_run()["revised_evidence"])
    assert revised["freshness_after_source_edit"] == {
        "decision:retention": "stale",
        "decision:deployment": "current",
    }


def test_mutation_plan_reuses_unchanged_and_updates_revised_identity() -> None:
    revised = _as_dict(_run()["revised_evidence"])
    assert revised["mutation_operations"] == {
        "decision:retention": "update",
        "decision:deployment": "noop",
    }
    assert revised["projected_retention"] == "Customer data retention is ninety days."
    assert revised["retention_revision"] == "v2"


def test_artifact_history_supersedes_previous_revision() -> None:
    revised = _as_dict(_run()["revised_evidence"])
    history = _as_dict(revised["artifact_history"])
    assert history["decision:retention"] == ("v1", "v2")
    assert history["decision:deployment"] == ("v1",)


def test_module_main_prints_json() -> None:
    completed = subprocess.run(
        [sys.executable, str(Path(brain.__file__))],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["passed"] is True
