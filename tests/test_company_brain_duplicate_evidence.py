"""Regression coverage for order-dependent duplicate document evidence.

Two provider records can share a structural ``document_id`` without being the
same document: a changed revision, or the same provider page observed in two
tenants. The document-consuming parsers used to build their citation allowance
map with ``{document.document_id: document for document in documents}``, so the
last record silently won and the accepted evidence depended on argument order.

These tests pin the corrected contract:

* conflicting duplicates raise ``ValueError`` before any model output is parsed,
  in either input order;
* identical repeated documents (including from a generator) are accepted and
  collapsed;
* single-document model-drift repair is unchanged.

They intentionally use local fixtures rather than the isolation example so the
core behavior is covered without depending on another owned module.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import replace
from typing import Any

import pytest

from mari_kit import KnowledgeDocument
from mari_kit.knowledge import (
    parse_answer,
    parse_answer_candidates,
    parse_claim_assessments,
    parse_decisions,
    parse_digest,
    parse_facts,
    parse_glossary,
    parse_impact,
)
from mari_kit.knowledge._documents import document_lookup

SOURCE = "confluence:acme"
QUESTION = "How long are enterprise refunds?"

REFUND_A = KnowledgeDocument(
    source_id=SOURCE,
    external_id="page:refunds",
    title="Refund policy",
    body="Tenant A enterprise refunds are issued within 30 days.",
    revision="a-refunds-1",
)
REFUND_B = KnowledgeDocument(
    source_id=SOURCE,
    external_id="page:refunds",
    title="Refund policy",
    body="Tenant B enterprise refunds are issued within 14 days.",
    revision="b-refunds-1",
)

_CONFLICTING = ((REFUND_A, REFUND_B), (REFUND_B, REFUND_A))


def _answer_output() -> dict[str, Any]:
    return {
        "answer": REFUND_B.body,
        "evidence": [
            {"document_id": REFUND_B.document_id, "quote": REFUND_B.body},
        ],
    }


def _evidence() -> list[dict[str, str]]:
    return [{"document_id": REFUND_B.document_id, "quote": REFUND_B.body}]


def _invoke(name: str) -> Callable[[Iterable[KnowledgeDocument]], object]:
    """Return an invoker for each parser callsite that consumes documents."""

    calls: dict[str, Callable[[Iterable[KnowledgeDocument]], object]] = {
        "parse_answer": lambda documents: parse_answer(
            QUESTION, documents, _answer_output()
        ),
        "parse_answer_candidates": lambda documents: parse_answer_candidates(
            documents,
            {
                "answers": [
                    {
                        "question": QUESTION,
                        "answer": REFUND_B.body,
                        "evidence": _evidence(),
                    }
                ]
            },
        ),
        "parse_facts": lambda documents: parse_facts(
            documents,
            {"facts": [{"claim": REFUND_B.body, "evidence": _evidence()}]},
        ),
        "parse_claim_assessments": lambda documents: parse_claim_assessments(
            [REFUND_B.body],
            documents,
            {
                "assessments": [
                    {
                        "claim": REFUND_B.body,
                        "verdict": "supported",
                        "evidence": _evidence(),
                    }
                ]
            },
        ),
        "parse_decisions": lambda documents: parse_decisions(
            documents,
            {"decisions": [{"statement": REFUND_B.body, "evidence": _evidence()}]},
        ),
        "parse_glossary": lambda documents: parse_glossary(
            documents,
            {
                "terms": [
                    {
                        "term": "refund",
                        "definition": REFUND_B.body,
                        "evidence": _evidence(),
                    }
                ]
            },
        ),
        "parse_digest": lambda documents: parse_digest(
            documents,
            {
                "summary": REFUND_B.body,
                "topics": [
                    {
                        "title": "Refunds",
                        "summary": REFUND_B.body,
                        "evidence": _evidence(),
                    }
                ],
                "evidence": _evidence(),
            },
        ),
        "parse_impact": lambda documents: parse_impact(
            documents,
            {
                "summary": REFUND_B.body,
                "affected_document_ids": [REFUND_B.document_id],
                "evidence": _evidence(),
            },
        ),
    }
    return calls[name]


PARSER_NAMES = (
    "parse_answer",
    "parse_answer_candidates",
    "parse_facts",
    "parse_claim_assessments",
    "parse_decisions",
    "parse_glossary",
    "parse_digest",
    "parse_impact",
)


def test_fixture_documents_really_collide() -> None:
    assert REFUND_A.document_id == REFUND_B.document_id
    assert REFUND_A != REFUND_B
    assert REFUND_A.body != REFUND_B.body


def test_document_lookup_collapses_identical_and_rejects_conflicts() -> None:
    assert document_lookup((REFUND_A, REFUND_A)) == {REFUND_A.document_id: REFUND_A}
    assert document_lookup((REFUND_A, replace(REFUND_A))) == {
        REFUND_A.document_id: REFUND_A
    }
    for documents in _CONFLICTING:
        with pytest.raises(ValueError, match="conflicting documents share document_id"):
            document_lookup(documents)


@pytest.mark.parametrize("name", PARSER_NAMES)
def test_conflicting_documents_are_rejected_in_either_order(name: str) -> None:
    invoke = _invoke(name)
    for documents in _CONFLICTING:
        with pytest.raises(ValueError, match="conflicting documents share document_id"):
            invoke(documents)


@pytest.mark.parametrize("name", PARSER_NAMES)
def test_conflict_is_rejected_before_model_output_is_parsed(name: str) -> None:
    with pytest.raises(ValueError, match="conflicting documents share document_id"):
        _invoke_with_output(name, object())


def _invoke_with_output(name: str, model_output: object) -> object:
    if name == "parse_answer":
        return parse_answer(QUESTION, _CONFLICTING[0], model_output)
    if name == "parse_answer_candidates":
        return parse_answer_candidates(_CONFLICTING[0], model_output)
    if name == "parse_facts":
        return parse_facts(_CONFLICTING[0], model_output)
    if name == "parse_claim_assessments":
        return parse_claim_assessments(["claim"], _CONFLICTING[0], model_output)
    if name == "parse_decisions":
        return parse_decisions(_CONFLICTING[0], model_output)
    if name == "parse_glossary":
        return parse_glossary(_CONFLICTING[0], model_output)
    if name == "parse_digest":
        return parse_digest(_CONFLICTING[0], model_output)
    return parse_impact(_CONFLICTING[0], model_output)


@pytest.mark.parametrize("name", PARSER_NAMES)
def test_exact_repeats_from_a_generator_are_accepted(name: str) -> None:
    def documents() -> Iterable[KnowledgeDocument]:
        yield REFUND_B
        yield REFUND_B

    result = _invoke(name)(documents())
    assert result is not None


def test_identical_repeats_accept_evidence_independently_of_order() -> None:
    forward = parse_answer(QUESTION, (REFUND_B, REFUND_B), _answer_output())
    reversed_order = parse_answer(
        QUESTION, (REFUND_B, replace(REFUND_B)), _answer_output()
    )
    assert forward == reversed_order
    assert forward.evidence[0].document_id == REFUND_B.document_id
    assert forward.evidence[0].revision == REFUND_B.revision


def test_conflicting_documents_never_reach_evidence_binding() -> None:
    drifted = {
        "facts": [
            {
                "claim": "refunds are issued",
                "evidence": [{"quote": REFUND_A.body}],
            }
        ]
    }
    assert parse_facts((REFUND_A,), drifted)[0].evidence[0].document_id == (
        REFUND_A.document_id
    )
    with pytest.raises(ValueError, match="conflicting documents share document_id"):
        parse_facts((REFUND_A, REFUND_B), drifted)
