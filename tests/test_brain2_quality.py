"""Behavioral tests for the wave-2 company brain quality corpus and evaluator."""

from __future__ import annotations

import json

import pytest

from examples.company_brains.durable.quality_corpus import (
    ABSTENTION_TEXT,
    CATEGORIES,
    DISPOSITIONS,
    GRADING_FIELDS,
    authorized_documents,
    build_prompt,
    cases,
)
from examples.company_brains.durable.quality_eval import (
    default_generate,
    evaluate_case,
    run,
)
from mari_kit import KnowledgeDocument

REQUIRED_CASE_KEYS = {
    "id",
    "category",
    "question",
    "documents",
    "expected_disposition",
    "required_terms",
    "forbidden_terms",
    "allowed_evidence_ids",
}


def _identity(document: KnowledgeDocument) -> tuple[str, str]:
    return document.document_id, document.revision


def _case(case_id: str) -> dict:
    return next(case for case in cases() if case["id"] == case_id)


def _prediction(
    document: KnowledgeDocument, answer: str, *, revision: str = ""
) -> dict:
    return {
        "answer": answer,
        "disposition": "grounded",
        "evidence": [
            {
                "document_id": document.document_id,
                "revision": revision or document.revision,
                "quote": document.body,
            }
        ],
    }


def test_cases_meet_scale_and_shared_schema():
    corpus = cases()
    assert len(corpus) >= 24
    assert len({case["id"] for case in corpus}) == len(corpus)

    seen_categories: set[str] = set()
    for case in corpus:
        assert REQUIRED_CASE_KEYS <= set(case)
        assert case["category"] in CATEGORIES
        assert case["expected_disposition"] in DISPOSITIONS
        assert case["question"].strip()
        assert case["documents"]
        assert all(isinstance(doc, KnowledgeDocument) for doc in case["documents"])
        assert (case["expected_disposition"] == "grounded") == bool(
            case["allowed_evidence_ids"]
        )
        seen_categories.add(case["category"])

    assert seen_categories == set(CATEGORIES)


def test_prompt_builder_returns_only_question_and_authorized_documents():
    corpus = cases()
    assert any(
        len(case["documents"]) > len(authorized_documents(case)) for case in corpus
    )

    for case in corpus:
        prompt = build_prompt(case)
        assert set(prompt) == {"question", "documents"}
        assert not (set(prompt) & GRADING_FIELDS)
        assert prompt["question"] == case["question"]
        prompt_docs = {_identity(doc) for doc in prompt["documents"]}
        authorized = {_identity(doc) for doc in authorized_documents(case)}
        assert prompt_docs == authorized
        assert prompt_docs <= {_identity(doc) for doc in case["documents"]}


def test_prompt_withholds_retired_revision_and_restricted_evidence():
    superseded = _case("superseded.refund_window")
    prompt = build_prompt(superseded)
    prompt_docs = {_identity(doc) for doc in prompt["documents"]}
    assert ("handbook/refunds", "refund-v2") not in prompt_docs
    assert ("handbook/refunds", "refund-v2") in {
        _identity(doc) for doc in superseded["documents"]
    }

    restricted = _case("restricted.compensation")
    prompt_docs = {_identity(doc) for doc in build_prompt(restricted)["documents"]}
    assert ("hr/compensation", "comp-v1") not in prompt_docs
    assert prompt_docs == {_identity(doc) for doc in authorized_documents(restricted)}


def test_grounded_prediction_scores_each_metric_separately():
    case = _case("current.refund_window")
    document = authorized_documents(case)[0]
    result = evaluate_case(
        case, _prediction(document, "The enterprise refund window is 45 days.")
    )
    assert result["prediction_valid"] is True
    assert result["grounded"] is True
    assert result["citation_valid"] is True
    assert result["answer_correct"] is True
    assert result["disposition_correct"] is True
    assert result["abstained"] is False
    assert result["stale"] is False
    assert result["current_citations"] == 1


def test_fabricated_citation_is_invalid_and_still_counted():
    case = _case("current.refund_window")
    prediction = {
        "answer": "Refunds are unlimited.",
        "disposition": "grounded",
        "evidence": [
            {"document_id": "ghost/document", "quote": "Refunds are unlimited."}
        ],
    }
    result = evaluate_case(case, prediction)
    assert result["prediction_valid"] is False
    assert result["citation_valid"] is False
    assert result["disposition_correct"] is False
    assert result["answer_correct"] is False
    assert result["fabricated_citations"] == 1
    assert result["error"]


def test_unauthorized_citation_is_invalid_and_counted_as_unauthorized():
    case = _case("restricted.compensation")
    restricted = next(
        doc for doc in case["documents"] if doc.document_id == "hr/compensation"
    )
    result = evaluate_case(case, _prediction(restricted, "The band is $210,000."))
    assert result["prediction_valid"] is False
    assert result["citation_valid"] is False
    assert result["unauthorized_citations"] == 1


def test_stale_revision_is_flagged_even_when_quote_is_current():
    case = _case("superseded.refund_window")
    document = authorized_documents(case)[0]
    result = evaluate_case(
        case, _prediction(document, "Refund window is 45 days.", revision="refund-v2")
    )
    assert result["prediction_valid"] is True
    assert result["stale"] is True
    assert result["citation_valid"] is False
    assert result["stale_citations"] == 1


def test_abstention_is_scored_against_the_expected_disposition():
    grounded_case = _case("current.refund_window")
    abstention = {
        "answer": ABSTENTION_TEXT,
        "disposition": "insufficient_evidence",
        "evidence": [],
    }
    missed = evaluate_case(grounded_case, abstention)
    assert missed["abstained"] is True
    assert missed["disposition_correct"] is False
    assert missed["answer_correct"] is False

    abstain_case = _case("missing.soc2")
    hit = evaluate_case(abstain_case, abstention)
    assert hit["abstained"] is True
    assert hit["disposition_correct"] is True
    assert hit["answer_correct"] is None


def test_fixture_run_is_deterministic_json_with_explicit_denominators():
    first = run()
    second = run()
    assert first == second
    json.dumps(first)

    metrics = first["metrics"]
    assert first["mode"] == "fixture"
    assert metrics["case_count"] == len(cases())

    expected_grounded = sum(
        case["expected_disposition"] == "grounded" for case in cases()
    )
    assert metrics["citation_validity"]["total"] == expected_grounded
    assert metrics["answer_correctness_proxy"]["total"] == expected_grounded
    assert metrics["disposition_accuracy"]["total"] == metrics["case_count"]
    assert metrics["abstention"]["total"] == metrics["case_count"]
    assert metrics["abstention"]["accuracy"]["total"] == metrics["case_count"]

    attempts = sum(result["grounded_attempt"] for result in first["cases"])
    assert metrics["stale"]["total"] == attempts
    assert (
        metrics["invalid_outputs"]["count"]
        + sum(result["prediction_valid"] for result in first["cases"])
        == metrics["case_count"]
    )
    for key in (
        "citation_validity",
        "answer_correctness_proxy",
        "disposition_accuracy",
    ):
        assert 0.0 <= metrics[key]["rate"] <= 1.0
    assert 0.0 <= metrics["stale"]["rate"] <= 1.0


def test_default_generate_is_offline_and_respects_abstention():
    case = _case("missing.soc2")
    prediction = default_generate(case["question"], authorized_documents(case))
    result = evaluate_case(case, prediction)
    assert result["prediction_valid"] is True


def test_live_callback_receives_only_authorized_inputs():
    calls: list[tuple[str, tuple]] = []

    def generate(question: str, documents: tuple) -> dict:
        calls.append((question, documents))
        return {
            "answer": ABSTENTION_TEXT,
            "disposition": "insufficient_evidence",
            "evidence": [],
        }

    out = run(generate=generate)
    assert out["mode"] == "live"
    assert len(calls) == len(cases())
    for (question, documents), case in zip(calls, cases(), strict=True):
        assert question == case["question"]
        assert {_identity(doc) for doc in documents} == {
            _identity(doc) for doc in authorized_documents(case)
        }
    assert out["metrics"]["abstention"]["abstained"] == out["metrics"]["case_count"]


def test_callback_exception_counts_as_invalid_output_not_dropped():
    target = cases()[0]["question"]

    def generate(question: str, documents: tuple) -> dict:
        if question == target:
            raise RuntimeError("model unavailable")
        return {
            "answer": ABSTENTION_TEXT,
            "disposition": "insufficient_evidence",
            "evidence": [],
        }

    out = run(generate=generate)
    metrics = out["metrics"]
    assert metrics["invalid_outputs"]["count"] == 1
    assert metrics["invalid_outputs"]["total"] == metrics["case_count"]
    assert metrics["disposition_accuracy"]["total"] == metrics["case_count"]
    failed = next(result for result in out["cases"] if result["id"] == cases()[0]["id"])
    assert failed["error"].startswith("generate_error")


def test_live_stale_prediction_increases_stale_rate():
    stale_question = "How long is the enterprise refund window today?"

    def generate(question: str, documents: tuple) -> dict:
        document = documents[0]
        if question == stale_question:
            return {
                "answer": "The refund window is 45 days.",
                "disposition": "grounded",
                "evidence": [
                    {
                        "document_id": document.document_id,
                        "revision": "refund-v2",
                        "quote": document.body,
                    }
                ],
            }
        return {
            "answer": ABSTENTION_TEXT,
            "disposition": "insufficient_evidence",
            "evidence": [],
        }

    out = run(generate=generate)
    assert out["metrics"]["stale"]["stale"] >= 1
    assert out["metrics"]["stale"]["total"] >= 1


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_category_has_at_least_one_case(category):
    assert any(case["category"] == category for case in cases())
