"""Deterministic tests for the wave-3 company brain quality corpus and runner.

Every test here is offline and label-driven. They pin the corpus size and shape,
prove that model-visible input is source-only, and verify that each gold label is
objectively supported by the source text rather than by the author's intent.
"""

from __future__ import annotations

import json

import pytest

from examples.company_brains.durable import quality_wave3
from examples.company_brains.durable.live_eval import ANSWER_INSTRUCTION, source_input
from examples.company_brains.durable.quality_corpus import (
    DISPOSITIONS as EVAL_DISPOSITIONS,
)
from examples.company_brains.durable.quality_eval import evaluate_case

SCHEMA_KEYS = {
    "id",
    "category",
    "question",
    "documents",
    "authorized_documents",
    "authorized_document_ids",
    "expected_disposition",
    "required_terms",
    "forbidden_terms",
    "allowed_evidence_ids",
    "allowed_evidence_refs",
}

SOURCE_FIELDS = {"document_id", "revision", "title", "body"}


def _by_id(case_id: str) -> dict:
    return next(case for case in quality_wave3.cases() if case["id"] == case_id)


def _visible_text(case: dict) -> str:
    return "\n".join(
        document.body for document in case["authorized_documents"]
    ).casefold()


def _allowed_documents(case: dict) -> list:
    allowed = set(case["allowed_evidence_ids"])
    return [
        document
        for document in case["authorized_documents"]
        if document.document_id in allowed
    ]


def test_corpus_is_frozen_sized_and_categorically_complete():
    corpus = quality_wave3.cases()
    assert 12 <= len(corpus) <= 16
    assert {case["id"] for case in corpus} == {
        case["id"] for case in quality_wave3.snapshot()
    }
    assert len({case["id"] for case in corpus}) == len(corpus)
    assert {case["category"] for case in corpus} == set(quality_wave3.CATEGORIES)
    assert quality_wave3.DISPOSITIONS == EVAL_DISPOSITIONS


def test_cases_match_the_wave2_schema_and_disposition_contract():
    for case in quality_wave3.cases():
        assert SCHEMA_KEYS <= set(case)
        assert case["category"] in quality_wave3.CATEGORIES
        assert case["expected_disposition"] in quality_wave3.DISPOSITIONS
        assert case["question"].strip()
        assert case["documents"]
        assert all(
            isinstance(document, quality_wave3.KnowledgeDocument)
            for document in case["documents"]
        )
        assert (case["expected_disposition"] == "grounded") == bool(
            case["allowed_evidence_ids"]
        )


def test_prompt_inputs_are_source_only_and_exclude_grading_labels():
    payload = quality_wave3.prompt_inputs(
        {
            "id": "secret-case-id",
            "question": "Question?",
            "documents": (),
            "authorized_documents": (),
            "authorized_document_ids": [],
            "expected_disposition": "insufficient_evidence",
            "required_terms": ["hidden-gold-answer"],
            "forbidden_terms": ["private-grading-rule"],
            "allowed_evidence_ids": ["secret-evidence-id"],
            "allowed_evidence_refs": [
                {"document_id": "secret-evidence-id", "revision": "v"}
            ],
            "gold_basis": "secret-gold-basis",
        }
    )
    assert set(payload) == {"question", "documents"}
    assert not (set(payload) & quality_wave3.GRADING_FIELDS)
    encoded = json.dumps(payload)
    for sentinel in (
        "secret-case-id",
        "hidden-gold-answer",
        "private-grading-rule",
        "secret-evidence-id",
        "secret-gold-basis",
    ):
        assert sentinel not in encoded


def test_prompt_inputs_reuse_the_live_evaluator_whitelist():
    for case in quality_wave3.cases():
        payload = quality_wave3.prompt_inputs(case)
        assert payload == source_input(case)
        assert set(payload) == {"question", "documents"}
        assert payload["question"] == case["question"]
        visible = {document.document_id for document in case["authorized_documents"]}
        assert [row["document_id"] for row in payload["documents"]] == [
            document.document_id for document in case["authorized_documents"]
        ]
        assert all(set(row) == SOURCE_FIELDS for row in payload["documents"])
        assert {row["document_id"] for row in payload["documents"]} == visible
        assert len(visible) == len(case["authorized_documents"])
        assert case["id"] not in json.dumps(payload)
        assert case["gold_basis"] not in json.dumps(payload)


def test_grounded_gold_is_supported_by_the_allowed_evidence():
    grounded = [
        case
        for case in quality_wave3.cases()
        if case["expected_disposition"] == "grounded"
    ]
    assert len(grounded) >= 4
    for case in grounded:
        bodies = " \n ".join(document.body for document in _allowed_documents(case))
        folded = bodies.casefold()
        assert case["required_terms"]
        for term in case["required_terms"]:
            assert term.casefold() in folded, (case["id"], "required", term)
        for term in case["forbidden_terms"]:
            factual_text = folded.split("note to assistant:", 1)[0]
            assert term.casefold() not in factual_text, (case["id"], "forbidden", term)
        allowed_ids = {document.document_id for document in _allowed_documents(case)}
        assert allowed_ids == set(case["allowed_evidence_ids"])
        assert allowed_ids <= {
            document.document_id for document in case["authorized_documents"]
        }


def test_abstention_gold_has_no_allowed_evidence_or_required_terms():
    abstaining = [
        case
        for case in quality_wave3.cases()
        if case["expected_disposition"] == "insufficient_evidence"
    ]
    assert len(abstaining) >= 4
    for case in abstaining:
        assert case["allowed_evidence_ids"] == []
        assert case["allowed_evidence_refs"] == []
        assert case["required_terms"] == []


def test_missing_region_abstention_is_objectively_supported():
    brazil = _by_id("region.brazil_missing")
    visible = _visible_text(brazil)
    assert "brazil" not in visible
    assert "united states" in visible and "european union" in visible

    global_case = _by_id("region.no_global_default")
    assert "no global default" in _visible_text(global_case)
    assert global_case["expected_disposition"] == "grounded"

    supported = _by_id("region.us_supported")
    assert supported["expected_disposition"] == "grounded"
    assert "30 days" in _visible_text(supported)


def test_superseded_pairs_are_visible_with_distinct_document_ids():
    for case_id in ("superseded.refund_window", "superseded.password_rotation"):
        case = _by_id(case_id)
        visible_ids = [
            document.document_id for document in case["authorized_documents"]
        ]
        assert len(visible_ids) == len(set(visible_ids)) == 2
        assert set(visible_ids) == {
            document.document_id for document in case["documents"]
        }
        assert len(case["allowed_evidence_ids"]) == 1
        current_id = case["allowed_evidence_ids"][0]
        current = next(
            document
            for document in case["authorized_documents"]
            if document.document_id == current_id
        ).body.casefold()
        assert "current" in current or "supersedes" in current
        old_id = next(item for item in visible_ids if item != current_id)
        old = next(
            document
            for document in case["authorized_documents"]
            if document.document_id == old_id
        ).body.casefold()
        assert any(word in old for word in ("superseded", "archived", "replaced"))

    archived = _by_id("superseded.archived_no_replacement")
    assert archived["expected_disposition"] == "insufficient_evidence"
    assert "no replacement" in _visible_text(archived)


def test_restricted_evidence_is_present_but_withheld_from_the_prompt():
    for case_id, restricted_id in (
        ("restricted.compensation", "hr/compensation"),
        ("restricted.settlement", "legal/acme-settlement"),
    ):
        case = _by_id(case_id)
        corpus_ids = {document.document_id for document in case["documents"]}
        visible_ids = {
            document.document_id for document in case["authorized_documents"]
        }
        assert restricted_id in corpus_ids
        assert restricted_id not in visible_ids
        restricted = next(
            document
            for document in case["documents"]
            if document.document_id == restricted_id
        )
        assert restricted.acl.visibility == "restricted"
        assert case["expected_disposition"] == "insufficient_evidence"


def test_adversarial_sources_carry_injected_instructions_that_are_not_evidence():
    incident = _by_id("adversarial.incident_paging")
    assert incident["expected_disposition"] == "grounded"
    body = _allowed_documents(incident)[0].body
    assert "5 minutes" in body
    assert "NOTE TO ASSISTANT" in body

    pure = _by_id("adversarial.pure_injection")
    assert pure["expected_disposition"] == "insufficient_evidence"
    assert "no factual schedule" in _visible_text(pure)


def test_labels_and_grades_are_deterministic():
    assert quality_wave3.cases() == quality_wave3.cases()

    for case in quality_wave3.cases():
        if case["expected_disposition"] == "grounded":
            document = _allowed_documents(case)[0]
            prediction = {
                "answer": " ".join(case["required_terms"]),
                "disposition": "grounded",
                "evidence": [
                    {
                        "document_id": document.document_id,
                        "revision": document.revision,
                        "quote": document.body,
                    }
                ],
            }
            first = evaluate_case(case, prediction)
            assert first == evaluate_case(case, prediction)
            assert first["answer_correct"] is True
            assert first["citation_valid"] is True
        else:
            prediction = {
                "answer": quality_wave3.ABSTENTION_TEXT,
                "disposition": "insufficient_evidence",
                "evidence": [],
            }
            first = evaluate_case(case, prediction)
            assert first == evaluate_case(case, prediction)
            assert first["abstained"] is True
            assert first["disposition_correct"] is True


def test_superseded_value_is_graded_wrong_even_when_visible():
    case = _by_id("superseded.refund_window")
    old = next(
        document
        for document in case["authorized_documents"]
        if document.document_id == "handbook/refunds-2023"
    )
    prediction = {
        "answer": "The refund window is 30 days.",
        "disposition": "grounded",
        "evidence": [
            {
                "document_id": old.document_id,
                "revision": old.revision,
                "quote": old.body,
            }
        ],
    }
    result = evaluate_case(case, prediction)
    assert result["answer_correct"] is False
    assert result["stale_content_proxy"] is True
    assert result["stale"] is True


def test_corpus_hash_is_stable_and_input_sensitive():
    first = quality_wave3.corpus_sha256()
    assert first == quality_wave3.corpus_sha256(quality_wave3.snapshot())
    assert len(first) == 64

    frozen = list(quality_wave3.snapshot())
    frozen[0] = {**frozen[0], "question": frozen[0]["question"] + " (tampered)"}
    assert quality_wave3.corpus_sha256(frozen) != first


def test_live_runner_hashes_before_any_request_and_keeps_inputs_source_only(
    monkeypatch,
):
    events: list[str] = []

    def fake_hash(corpus=None):
        events.append("hash")
        return "f" * 64

    def fake_request(system, payload, *, model, max_tokens=3000):
        events.append("request")
        return (
            {
                "answer": quality_wave3.ABSTENTION_TEXT,
                "disposition": "insufficient_evidence",
                "evidence": [],
            },
            {"usage": {}},
        )

    monkeypatch.setattr(quality_wave3, "corpus_sha256", fake_hash)
    monkeypatch.setattr(quality_wave3, "request_json", fake_request)

    report = quality_wave3.evaluate_live(limit=2, workers=1)
    assert report["mode"] == "live_wave3"
    assert report["corpus_sha256"] == "f" * 64
    assert report["corpus_case_count"] == len(quality_wave3.cases())
    assert events[0] == "hash"
    assert events.index("hash") < events.index("request")
    assert events.count("request") == 2
    assert report["answer_request_failures"] == 0

    for row in report["results"]:
        assert "answer_error" not in row
        assert set(row["model_input"]) == {"question", "documents"}
        assert all(
            set(document) == SOURCE_FIELDS
            for document in row["model_input"]["documents"]
        )
        assert row["model_input"]["question"] in [
            case["question"] for case in quality_wave3.cases()
        ]

    encoded = json.dumps([row["model_input"] for row in report["results"]])
    for case in quality_wave3.cases()[:2]:
        assert case["id"] not in encoded
        assert case["gold_basis"] not in encoded


def test_live_runner_records_request_failure_as_invalid_output(monkeypatch):
    def failing_request(system, payload, *, model, max_tokens=3000):
        assert system == ANSWER_INSTRUCTION
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(quality_wave3, "request_json", failing_request)
    report = quality_wave3.evaluate_live(limit=1, workers=1)
    assert report["answer_request_failures"] == 1
    row = report["results"][0]
    assert row["answer_error"].startswith("RuntimeError")
    assert row["metrics"]["prediction_valid"] is False
    assert report["summary"]["invalid_outputs"]["count"] == 1


def test_cli_requires_live_and_output_then_writes_report(monkeypatch, tmp_path):
    with pytest.raises(SystemExit):
        quality_wave3.build_parser().parse_args([])
    with pytest.raises(SystemExit):
        quality_wave3.build_parser().parse_args(["--live"])

    sentinel = {"mode": "live_wave3", "corpus_sha256": "a" * 64, "results": []}
    monkeypatch.setattr(quality_wave3, "evaluate_live", lambda **kwargs: sentinel)
    output = tmp_path / "quality-wave3.json"
    quality_wave3.main(["--live", "--output", str(output)])
    written = json.loads(output.read_text())
    assert written == sentinel
