"""Independent adversarial audit of the wave-2 company-brain quality corpus.

These tests are owned by the quality reviewer, not the corpus author. They
deliberately re-derive the answerability and leakage properties of every case
from the public case schema instead of reusing the builder's own evaluator.
They depend on ``examples.company_brains.durable`` source files owned by other
agents and are expected to fail at collection if those files are absent.
"""

from __future__ import annotations

import json
import re

from examples.company_brains.durable import quality_corpus, quality_eval

CASE_KEYS = {
    "id",
    "category",
    "question",
    "documents",
    "expected_disposition",
    "required_terms",
    "forbidden_terms",
    "allowed_evidence_ids",
}
REQUIRED_CATEGORY_CONCEPTS = (
    "current",
    "superseded",
    "conflict",
    "ambig",
    "missing",
    "restricted",
    "irrelevant",
)
LEAK_MARKERS = (
    "expected_disposition",
    "required_terms",
    "forbidden_terms",
    "allowed_evidence",
    "insufficient_evidence",
    "gold_answer",
)
TOKEN = re.compile(r"[a-z0-9]+")


def term_supported(term: str, body: str) -> bool:
    normalized = term.casefold().strip()
    if normalized and normalized in body:
        return True
    tokens = TOKEN.findall(normalized)
    return bool(tokens) and set(tokens) <= set(TOKEN.findall(body))


def document_text(case: dict) -> str:
    return "\n".join(
        f"{document.title}\n{document.body}" for document in case["documents"]
    ).casefold()


def allowed_bodies(case: dict) -> str:
    by_id = {document.document_id: document for document in case["documents"]}
    return "\n".join(
        by_id[document_id].body for document_id in case["allowed_evidence_ids"]
    ).casefold()


def gold_prediction(case: dict) -> dict:
    by_id = {document.document_id: document for document in case["documents"]}
    evidence = [
        {
            "document_id": document_id,
            "revision": by_id[document_id].revision,
            "quote": by_id[document_id].body,
        }
        for document_id in case["allowed_evidence_ids"]
    ]
    if case["expected_disposition"] == "insufficient_evidence":
        return {
            "answer": "The available documents do not contain this information.",
            "disposition": "insufficient_evidence",
            "evidence": [],
        }
    return {
        "answer": " ".join(case["required_terms"]),
        "disposition": "grounded",
        "evidence": evidence,
    }


def cases() -> list[dict]:
    return list(quality_corpus.cases())


# --- corpus shape and coverage ----------------------------------------------


def test_corpus_has_at_least_24_unique_cases_with_required_keys() -> None:
    corpus = cases()
    assert len(corpus) >= 24
    ids = [case["id"] for case in corpus]
    assert len(ids) == len(set(ids))
    for case in corpus:
        assert CASE_KEYS <= case.keys(), case["id"]
        assert case["id"].strip() and case["question"].strip()
        assert case["category"].strip()
        assert case["expected_disposition"] in {
            "grounded",
            "insufficient_evidence",
        }, case["id"]
        assert isinstance(case["required_terms"], list)
        assert isinstance(case["forbidden_terms"], list)
        assert isinstance(case["allowed_evidence_ids"], list)
        assert case["documents"], case["id"]


def test_corpus_covers_required_category_concepts() -> None:
    categories = " ".join(case["category"].casefold() for case in cases())
    missing = [
        concept for concept in REQUIRED_CATEGORY_CONCEPTS if concept not in categories
    ]
    assert not missing, f"missing category concepts: {missing}"


def test_corpus_spans_varied_company_domains() -> None:
    sources = {document.source_id for case in cases() for document in case["documents"]}
    assert len(sources) >= 4, sorted(sources)


# --- label and evidence consistency -----------------------------------------


def test_labels_are_valid_and_evidence_is_a_subset_of_case_documents() -> None:
    for case in cases():
        document_ids = {document.document_id for document in case["documents"]}
        assert set(case["allowed_evidence_ids"]) <= document_ids, case["id"]
        assert len(case["allowed_evidence_ids"]) == len(
            set(case["allowed_evidence_ids"])
        ), case["id"]
        if case["expected_disposition"] == "grounded":
            assert case["allowed_evidence_ids"], case["id"]
            assert case["required_terms"], case["id"]
        else:
            assert not case["allowed_evidence_ids"], case["id"]


def test_grounded_required_terms_are_answerable_from_allowed_evidence() -> None:
    defects: list[str] = []
    for case in cases():
        if case["expected_disposition"] != "grounded":
            continue
        body = allowed_bodies(case)
        for term in case["required_terms"]:
            if not term_supported(term, body):
                defects.append(f"{case['id']}: required term {term!r} absent")
    assert not defects, defects


def test_forbidden_terms_do_not_appear_in_allowed_evidence() -> None:
    defects: list[str] = []
    for case in cases():
        body = allowed_bodies(case)
        for term in case["forbidden_terms"]:
            if term.casefold() in body:
                defects.append(f"{case['id']}: forbidden term {term!r} is in evidence")
    assert not defects, defects


def test_required_and_forbidden_terms_are_disjoint() -> None:
    for case in cases():
        required = {term.casefold() for term in case["required_terms"]}
        forbidden = {term.casefold() for term in case["forbidden_terms"]}
        assert not (required & forbidden), case["id"]


def test_distractor_cases_place_forbidden_terms_in_disallowed_documents() -> None:
    distractor_concepts = (
        "conflict",
        "superseded",
        "restricted",
        "irrelevant",
        "ambig",
    )
    defects: list[str] = []
    for case in cases():
        if not case["forbidden_terms"]:
            continue
        if not any(
            concept in case["category"].casefold() for concept in distractor_concepts
        ):
            continue
        allowed_ids = set(case["allowed_evidence_ids"])
        authorized = {
            (document.document_id, document.revision)
            for document in case["authorized_documents"]
        }
        disallowed = "\n".join(
            document.body
            for document in case["documents"]
            if (document.document_id, document.revision) not in authorized
            or document.document_id not in allowed_ids
        ).casefold()
        if not any(term.casefold() in disallowed for term in case["forbidden_terms"]):
            defects.append(f"{case['id']}: no forbidden term appears in any distractor")
    assert not defects, defects


# --- evaluator-only label leakage -------------------------------------------


def test_evaluator_labels_do_not_leak_into_model_visible_text() -> None:
    defects: list[str] = []
    for case in cases():
        visible = f"{case['question']}\n{document_text(case)}".casefold()
        for marker in LEAK_MARKERS:
            if marker in visible:
                defects.append(f"{case['id']}: marker {marker!r} is model-visible")
    assert not defects, defects


def test_grounded_required_terms_are_not_entirely_quoted_in_the_question() -> None:
    # A gold term that appears verbatim in the question lets a degenerate answer
    # echo the prompt; it weakens the lexical correctness proxy. Recorded here so
    # the corpus author can see exactly which cases need a discriminative term.
    leaked = [
        case["id"]
        for case in cases()
        if case["expected_disposition"] == "grounded"
        and case["required_terms"]
        and all(
            term.casefold() in case["question"].casefold()
            for term in case["required_terms"]
        )
    ]
    assert not leaked, f"gold terms fully quoted in the question: {leaked}"


def test_no_gold_metadata_leaks_into_documents() -> None:
    label_fragments = (
        "expected",
        "required",
        "forbidden",
        "allowed_evidence",
        "disposition",
        "gold",
    )
    defects: list[str] = []
    for case in cases():
        for document in case["documents"]:
            for key in document.metadata:
                if any(fragment in str(key).casefold() for fragment in label_fragments):
                    defects.append(f"{case['id']}: metadata key {key!r}")
    assert not defects, defects


# --- evaluator metric contract ----------------------------------------------


def test_run_is_deterministic_and_json_serializable() -> None:
    first = quality_eval.run()
    second = quality_eval.run()
    assert first == second
    json.dumps(first)
    assert len(cases()) >= 24


def test_run_reports_separate_contract_metrics() -> None:
    serialized = json.dumps(quality_eval.run()).casefold()
    assert "citation" in serialized
    assert "stale" in serialized
    assert "abstain" in serialized
    assert "correct" in serialized


def test_invalid_output_is_graded_and_never_dropped() -> None:
    for case in cases():
        metrics = quality_eval.evaluate_case(case, {})
        assert isinstance(metrics, dict)
        json.dumps(metrics)


def test_invalid_output_scores_differently_from_a_supported_answer() -> None:
    for case in cases():
        gold = quality_eval.evaluate_case(case, gold_prediction(case))
        invalid = quality_eval.evaluate_case(case, {})
        assert gold != invalid, case["id"]


def test_grounded_answers_without_citations_do_not_grade_as_supported() -> None:
    case = next(case for case in cases() if case["expected_disposition"] == "grounded")
    uncited = {
        "answer": " ".join(case["required_terms"]),
        "disposition": "grounded",
        "evidence": [],
    }
    supported = quality_eval.evaluate_case(case, gold_prediction(case))
    assert quality_eval.evaluate_case(case, uncited) != supported


def test_stale_citation_metric_is_exercisable() -> None:
    case = next(item for item in cases() if item["id"] == "superseded.refund_window")
    current = case["authorized_documents"][0]
    superseded = next(
        document
        for document in case["documents"]
        if document.revision != current.revision
        and document.document_id == current.document_id
    )
    stale_prediction = {
        "answer": superseded.body,
        "disposition": "grounded",
        "evidence": [
            {
                "document_id": current.document_id,
                "revision": superseded.revision,
                "quote": current.body,
            }
        ],
    }
    metrics = quality_eval.evaluate_case(case, stale_prediction)
    assert metrics["stale"] is True
    assert metrics["stale_citations"] >= 1
    assert metrics["citation_valid"] is False


def test_unauthorized_citation_fails_citation_validity() -> None:
    case = next(item for item in cases() if item["id"] == "restricted.compensation")
    restricted = next(
        document
        for document in case["documents"]
        if document not in case["authorized_documents"]
    )
    metrics = quality_eval.evaluate_case(
        case,
        {
            "answer": restricted.body,
            "disposition": "grounded",
            "evidence": [
                {
                    "document_id": restricted.document_id,
                    "revision": restricted.revision,
                    "quote": restricted.body,
                }
            ],
        },
    )
    assert metrics["unauthorized_citations"] >= 1
    assert metrics["citation_valid"] is False


def test_fabricated_citation_fails_citation_validity() -> None:
    case = next(item for item in cases() if item["id"] == "current.pto")
    metrics = quality_eval.evaluate_case(
        case,
        {
            "answer": " ".join(case["required_terms"]),
            "disposition": "grounded",
            "evidence": [
                {
                    "document_id": "ghost/nowhere",
                    "revision": "v1",
                    "quote": "invented evidence",
                }
            ],
        },
    )
    assert metrics["fabricated_citations"] >= 1
    assert metrics["citation_valid"] is False
