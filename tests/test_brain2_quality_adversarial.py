"""Adversarial coverage for the wave-2 company-brain quality evaluator.

These tests pin the *contract* of ``examples/company_brains/durable/quality_eval``
and ``quality_corpus``. They are written by the quality breaker and intentionally
attack the evaluator with predictions that are individually plausible but wrong:

1. a perfectly cited wrong answer (valid quote, contradicts it);
2. a correct answer carrying a quote that does not exist in the source;
3. a citation to a fabricated source;
4. a required abstention answered with empty evidence;
5. a stale answer drawn from a superseded policy;
6. a citation to a source the host denies access to.

The evaluator must separate citation validity, answer-correctness proxy,
abstention and stale-answer rate. A prediction that cannot be parsed is still a
graded failure (it never disappears from the denominator), and the
evaluator-only fields (``expected_disposition``, ``required_terms``,
``forbidden_terms``, ``allowed_evidence_ids``) must never reach a generator
callback.

The metric adapter below deliberately matches dimensions by concept tokens
rather than by one hard-coded spelling, so an implementation may use either flat
keys (``citation_valid``) or nested ones (``citation.valid``) without weakening
the behavioral assertions.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from examples.company_brains.durable.quality_corpus import (
    GRADING_FIELDS,
    authorized_documents,
    build_prompt,
    cases,
)
from examples.company_brains.durable.quality_eval import evaluate_case, run
from mari_kit import KnowledgeDocument
from mari_kit.types import DocumentACL, Principal

CURRENT_QUOTE = "refunds are issued within 30 days of approval"
SUPERSEDED_QUOTE = "refunds are issued within 14 days of approval"
RESTRICTED_QUOTE = "refunds are issued within 45 days"
IRRELEVANT_QUOTE = "the kitchen is stocked every Monday morning"

CURRENT = KnowledgeDocument(
    source_id="confluence:acme",
    external_id="page:refund-current",
    title="Refund policy (current)",
    body=f"Current enterprise refund policy: {CURRENT_QUOTE}.",
    revision="refund-2026",
)
SUPERSEDED = KnowledgeDocument(
    source_id="confluence:acme",
    external_id="page:refund-current",
    title="Refund policy (superseded)",
    body=f"Superseded enterprise refund policy: {SUPERSEDED_QUOTE}.",
    revision="refund-2024",
)
RESTRICTED = KnowledgeDocument(
    source_id="confluence:acme",
    external_id="page:refund-legal",
    title="Restricted legal note",
    body=f"Restricted legal note: enterprise {RESTRICTED_QUOTE}.",
    revision="legal-1",
    acl=DocumentACL(
        visibility="restricted",
        principals=(Principal(kind="team", identifier="legal"),),
    ),
)
IRRELEVANT = KnowledgeDocument(
    source_id="confluence:acme",
    external_id="page:office-snacks",
    title="Office snacks",
    body=f"Office snack policy: {IRRELEVANT_QUOTE}.",
    revision="snacks-1",
)

GROUNDED_CASE: dict[str, Any] = {
    "id": "adv-ground-current",
    "category": "current_policy",
    "question": "How long do enterprise refunds take?",
    "documents": (CURRENT,),
    "expected_disposition": "grounded",
    "required_terms": ["30 days"],
    "forbidden_terms": ["14 days", "45 days"],
    "allowed_evidence_ids": [CURRENT.document_id],
    "authorized_document_ids": [CURRENT.document_id],
    "authorized_documents": (CURRENT,),
}

STALE_CASE: dict[str, Any] = {
    "id": "adv-stale-superseded",
    "category": "superseded_policy",
    "question": "How long do enterprise refunds take?",
    "documents": (SUPERSEDED, CURRENT),
    "expected_disposition": "grounded",
    "required_terms": ["30 days"],
    "forbidden_terms": ["14 days"],
    "allowed_evidence_ids": [CURRENT.document_id],
    "authorized_document_ids": [CURRENT.document_id],
    "authorized_documents": (CURRENT,),
}

ABSTAIN_CASE: dict[str, Any] = {
    "id": "adv-missing-info",
    "category": "missing_information",
    "question": "What is the enterprise refund SLA for Antarctica?",
    "documents": (IRRELEVANT,),
    "expected_disposition": "insufficient_evidence",
    "required_terms": [],
    "forbidden_terms": [],
    "allowed_evidence_ids": [],
    "authorized_document_ids": [IRRELEVANT.document_id],
    "authorized_documents": (IRRELEVANT,),
}

DENIED_CASE: dict[str, Any] = {
    "id": "adv-denied-source",
    "category": "restricted_evidence",
    "question": "What is the restricted legal refund position?",
    "documents": (RESTRICTED,),
    "expected_disposition": "insufficient_evidence",
    "required_terms": [],
    "forbidden_terms": [],
    "allowed_evidence_ids": [],
    "authorized_document_ids": [],
    "authorized_documents": (),
}

_DIMENSIONS: dict[str, tuple[tuple[str, ...], ...]] = {
    "citation_valid": (
        ("citation_valid",),
        ("citation", "valid"),
        ("valid", "citation"),
        ("evidence", "valid"),
    ),
    "answer_correct": (
        ("answer_correct",),
        ("answer", "correct"),
        ("correctness",),
    ),
    "abstained": (("abstain",),),
    "stale": (("stale",),),
    "prediction_valid": (("prediction_valid",), ("prediction", "valid")),
}

_EVALUATOR_LABELS = {
    "expected_disposition",
    "required_terms",
    "forbidden_terms",
    "allowed_evidence_ids",
}


def _prediction(
    *,
    answer: str,
    disposition: str,
    evidence: list[dict[str, str]] | None = None,
    cache_hit: bool = False,
) -> dict[str, Any]:
    return {
        "answer": answer,
        "disposition": disposition,
        "evidence": [] if evidence is None else evidence,
        "cache_hit": cache_hit,
    }


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, Mapping):
        flat: dict[str, Any] = {}
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            flat.update(_flatten(item, path))
        return flat
    return {prefix: value}


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return bool(value)


def _dimension(metrics: Mapping[str, Any], name: str) -> Any | None:
    flat = _flatten(metrics)
    for tokens in _DIMENSIONS[name]:
        matches = {
            path: value
            for path, value in flat.items()
            if all(token in path.lower() for token in tokens)
        }
        if not matches:
            continue
        booleans = {
            path: value for path, value in matches.items() if isinstance(value, bool)
        }
        chosen = booleans or matches
        return chosen[min(chosen, key=len)]
    return None


def _require(metrics: Mapping[str, Any], name: str) -> bool:
    value = _dimension(metrics, name)
    assert value is not None, (
        f"evaluate_case() exposes no separate {name!r} metric; "
        f"returned keys were {sorted(_flatten(metrics))}"
    )
    return _truthy(value)


def _contains_evaluator_label(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key) in _EVALUATOR_LABELS or _contains_evaluator_label(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_contains_evaluator_label(item) for item in value)
    return False


class TestCorpusContract:
    def test_corpus_has_at_least_twenty_four_cases(self) -> None:
        assert len(cases()) >= 24

    def test_case_ids_are_unique(self) -> None:
        ids = [case["id"] for case in cases()]
        assert len(ids) == len(set(ids))

    def test_every_case_has_the_contract_fields(self) -> None:
        required = {
            "id",
            "category",
            "question",
            "documents",
            "expected_disposition",
            "required_terms",
            "forbidden_terms",
            "allowed_evidence_ids",
        }
        for case in cases():
            assert required <= set(case), f"{case.get('id')} is missing fields"
            assert case["expected_disposition"] in {"grounded", "insufficient_evidence"}
            assert isinstance(case["question"], str) and case["question"].strip()
            assert isinstance(case["category"], str) and case["category"].strip()
            assert isinstance(case["required_terms"], list)
            assert isinstance(case["forbidden_terms"], list)
            assert isinstance(case["allowed_evidence_ids"], list)

    def test_case_documents_are_wellformed_and_uniquely_identified(self) -> None:
        for case in cases():
            documents = case["documents"]
            assert documents, f"{case['id']} has no documents"
            assert all(isinstance(doc, KnowledgeDocument) for doc in documents)
            # A superseded revision deliberately shares document_id with the
            # current revision, so identity is (document_id, revision).
            identities = [(doc.document_id, doc.revision) for doc in documents]
            assert len(identities) == len(set(identities)), case["id"]
            assert all(doc.body.strip() for doc in documents), case["id"]

    def test_allowed_evidence_ids_reference_case_documents_only(self) -> None:
        for case in cases():
            case_ids = {doc.document_id for doc in case["documents"]}
            assert set(case["allowed_evidence_ids"]) <= case_ids, case["id"]

    def test_authorized_ids_are_a_withheld_subset_of_the_corpus(self) -> None:
        for case in cases():
            case_ids = {doc.document_id for doc in case["documents"]}
            authorized = set(case["authorized_document_ids"])
            assert authorized <= case_ids, case["id"]
            visible = {doc.document_id for doc in authorized_documents(case)}
            assert visible == authorized, case["id"]

    def test_restricted_cases_withhold_the_restricted_document(self) -> None:
        restricted = [
            case for case in cases() if case["category"] == "restricted_evidence"
        ]
        assert restricted, "corpus must contain restricted-evidence cases"
        for case in restricted:
            hidden = [
                doc
                for doc in case["documents"]
                if doc.document_id not in case["authorized_document_ids"]
            ]
            assert hidden, case["id"]
            assert all(doc.acl.visibility == "restricted" for doc in hidden), case["id"]

    def test_grading_fields_are_the_documented_evaluator_only_labels(self) -> None:
        assert GRADING_FIELDS == {
            "expected_disposition",
            "required_terms",
            "forbidden_terms",
            "allowed_evidence_ids",
            "allowed_evidence_refs",
        }
        for case in cases():
            assert GRADING_FIELDS <= set(case), case["id"]

    def test_build_prompt_never_exposes_evaluator_labels(self) -> None:
        for case in cases():
            prompt = build_prompt(case)
            assert set(prompt) == {"question", "documents"}, case["id"]
            assert prompt["question"] == case["question"], case["id"]
            assert not _contains_evaluator_label(prompt), case["id"]
            exposed = {doc.document_id for doc in prompt["documents"]}
            assert exposed == set(case["authorized_document_ids"]), case["id"]

    def test_grounded_cases_expose_their_allowed_evidence_in_the_prompt(self) -> None:
        for case in cases():
            if case["expected_disposition"] != "grounded":
                continue
            exposed = {doc.document_id for doc in build_prompt(case)["documents"]}
            assert set(case["allowed_evidence_ids"]) <= exposed, case["id"]

    def test_withheld_restricted_documents_never_enter_a_prompt(self) -> None:
        for case in cases():
            exposed = {doc.document_id for doc in build_prompt(case)["documents"]}
            for doc in case["documents"]:
                if doc.acl.visibility == "restricted":
                    assert doc.document_id not in exposed, case["id"]

    def test_superseded_case_prompt_excludes_the_withheld_revision(self) -> None:
        case = next(
            item for item in cases() if item["id"] == "superseded.refund_window"
        )
        superseded_body = next(
            doc.body for doc in case["documents"] if "within 30 days" in doc.body
        )
        exposed_bodies = {doc.body for doc in build_prompt(case)["documents"]}
        assert superseded_body not in exposed_bodies, (
            "build_prompt filtered by document_id only, so the superseded revision "
            "sharing the current document_id leaked into the prompt"
        )

    def test_correct_current_answer_on_a_superseded_case_scores_as_grounded(
        self,
    ) -> None:
        case = next(
            item for item in cases() if item["id"] == "superseded.refund_window"
        )
        current = next(doc for doc in case["documents"] if "within 45 days" in doc.body)
        metrics = evaluate_case(
            case,
            _prediction(
                answer=current.body,
                disposition="grounded",
                evidence=[
                    {
                        "document_id": current.document_id,
                        "revision": current.revision,
                        "quote": current.body,
                    },
                ],
            ),
        )
        assert metrics["prediction_valid"] is True, metrics["error"]
        assert metrics["citation_valid"] is True
        assert metrics["answer_correct"] is True
        assert metrics["stale"] is False

    def test_required_and_forbidden_terms_do_not_overlap(self) -> None:
        for case in cases():
            required = {term.casefold() for term in case["required_terms"]}
            forbidden = {term.casefold() for term in case["forbidden_terms"]}
            assert required.isdisjoint(forbidden), case["id"]

    def test_categories_cover_the_required_concepts(self) -> None:
        categories = " ".join(case["category"].casefold() for case in cases())
        for concept in (
            "current",
            "superseded",
            "conflict",
            "ambig",
            "missing",
            "restricted",
            "irrelevant",
        ):
            assert concept in categories, f"no case category covers {concept!r}"


class TestMetricSeparation:
    def test_perfectly_cited_wrong_answer_valid_citation_but_incorrect(self) -> None:
        metrics = evaluate_case(
            GROUNDED_CASE,
            _prediction(
                answer="Enterprise refunds are issued within 14 days of approval.",
                disposition="grounded",
                evidence=[
                    {
                        "document_id": CURRENT.document_id,
                        "revision": CURRENT.revision,
                        "quote": CURRENT_QUOTE,
                    },
                ],
            ),
        )
        assert _require(metrics, "citation_valid") is True
        assert _require(metrics, "answer_correct") is False

    def test_correct_answer_with_nonexistent_quote_is_not_credited(self) -> None:
        correct_text = "Enterprise refunds are issued within 30 days of approval."
        grounded = evaluate_case(
            GROUNDED_CASE,
            _prediction(
                answer=correct_text,
                disposition="grounded",
                evidence=[
                    {
                        "document_id": CURRENT.document_id,
                        "revision": CURRENT.revision,
                        "quote": CURRENT_QUOTE,
                    },
                ],
            ),
        )
        broken = evaluate_case(
            GROUNDED_CASE,
            _prediction(
                answer=correct_text,
                disposition="grounded",
                evidence=[
                    {
                        "document_id": CURRENT.document_id,
                        "revision": CURRENT.revision,
                        "quote": "refunds are issued within 999 days of approval",
                    },
                ],
            ),
        )
        # Same answer text: the citation dimension alone separates the two.
        assert _require(grounded, "citation_valid") is True
        assert _require(broken, "citation_valid") is False
        # The nonexistent quote is an invalid output and counts as a failure.
        assert _require(broken, "prediction_valid") is False

    def test_fabricated_source_is_an_invalid_citation(self) -> None:
        metrics = evaluate_case(
            GROUNDED_CASE,
            _prediction(
                answer="Enterprise refunds are issued within 30 days of approval.",
                disposition="grounded",
                evidence=[
                    {
                        "document_id": "fabricated:source/page:ghost",
                        "revision": "ghost-1",
                        "quote": CURRENT_QUOTE,
                    },
                ],
            ),
        )
        assert _require(metrics, "citation_valid") is False
        assert metrics["fabricated_citations"] >= 1

    def test_required_abstention_with_empty_evidence_is_scored_as_abstained(
        self,
    ) -> None:
        metrics = evaluate_case(
            ABSTAIN_CASE,
            _prediction(
                answer="The available documents do not state the Antarctica refund SLA.",
                disposition="insufficient_evidence",
                evidence=[],
            ),
        )
        assert _require(metrics, "abstained") is True

    def test_required_abstention_without_explicit_disposition_is_abstained(
        self,
    ) -> None:
        metrics = evaluate_case(
            ABSTAIN_CASE,
            {
                "answer": "Not stated in the sources.",
                "evidence": [],
                "cache_hit": False,
            },
        )
        assert _require(metrics, "abstained") is True
        assert _require(metrics, "prediction_valid") is True

    def test_grounded_disposition_with_empty_evidence_is_invalid(self) -> None:
        metrics = evaluate_case(
            GROUNDED_CASE,
            {
                "answer": CURRENT.body,
                "disposition": "grounded",
                "evidence": [],
                "cache_hit": False,
            },
        )
        assert _require(metrics, "prediction_valid") is False
        assert _require(metrics, "citation_valid") is False

    def test_required_abstention_answered_with_evidence_is_not_abstention(self) -> None:
        metrics = evaluate_case(
            ABSTAIN_CASE,
            _prediction(
                answer="Enterprise refunds are issued within 30 days of approval.",
                disposition="grounded",
                evidence=[
                    {"document_id": IRRELEVANT.document_id, "quote": IRRELEVANT_QUOTE},
                ],
            ),
        )
        assert _require(metrics, "abstained") is False

    def test_stale_superseded_answer_is_flagged_separately(self) -> None:
        stale = evaluate_case(
            STALE_CASE,
            _prediction(
                answer="Enterprise refunds are issued within 14 days of approval.",
                disposition="grounded",
                evidence=[
                    {
                        "document_id": SUPERSEDED.document_id,
                        "revision": SUPERSEDED.revision,
                        "quote": SUPERSEDED_QUOTE,
                    },
                ],
            ),
        )
        assert _require(stale, "stale") is True
        assert _require(stale, "answer_correct") is False

        fresh = evaluate_case(
            STALE_CASE,
            _prediction(
                answer="Enterprise refunds are issued within 30 days of approval.",
                disposition="grounded",
                evidence=[
                    {
                        "document_id": CURRENT.document_id,
                        "revision": CURRENT.revision,
                        "quote": CURRENT_QUOTE,
                    },
                ],
            ),
        )
        assert _require(fresh, "stale") is False
        assert _require(fresh, "citation_valid") is True
        assert _require(fresh, "answer_correct") is True

    def test_denied_source_citation_is_invalid_even_when_quote_matches(self) -> None:
        metrics = evaluate_case(
            DENIED_CASE,
            _prediction(
                answer="Enterprise refunds are issued within 45 days.",
                disposition="grounded",
                evidence=[
                    {
                        "document_id": RESTRICTED.document_id,
                        "revision": RESTRICTED.revision,
                        "quote": RESTRICTED_QUOTE,
                    },
                ],
            ),
        )
        assert _require(metrics, "citation_valid") is False
        assert metrics["unauthorized_citations"] >= 1


class TestInvalidOutputPreserved:
    def test_invalid_prediction_keeps_every_dimension_and_counts_as_failure(
        self,
    ) -> None:
        valid = evaluate_case(
            GROUNDED_CASE,
            _prediction(
                answer="Enterprise refunds are issued within 30 days of approval.",
                disposition="grounded",
                evidence=[
                    {"document_id": CURRENT.document_id, "quote": CURRENT_QUOTE},
                ],
            ),
        )
        invalid = evaluate_case(GROUNDED_CASE, {})
        for name in _DIMENSIONS:
            assert _dimension(valid, name) is not None
            assert _dimension(invalid, name) is not None, (
                f"invalid output dropped the {name!r} metric instead of grading it"
            )
        assert _require(invalid, "answer_correct") is False
        assert _require(invalid, "citation_valid") is False

    def test_run_keeps_invalid_outputs_in_every_denominator(self) -> None:
        total = len(cases())
        grounded = sum(case["expected_disposition"] == "grounded" for case in cases())
        metrics = run(generate=lambda *args, **kwargs: {})["metrics"]
        assert metrics["invalid_outputs"]["count"] == total
        assert metrics["invalid_outputs"]["total"] == total
        assert metrics["citation_validity"]["total"] == grounded
        assert metrics["answer_correctness_proxy"]["total"] == grounded
        assert metrics["disposition_accuracy"]["total"] == total
        assert metrics["abstention"]["accuracy"]["total"] == total
        assert metrics["citation_validity"]["valid"] == 0
        assert metrics["answer_correctness_proxy"]["correct"] == 0

    def test_run_preserves_callback_exceptions_as_invalid_outputs(self) -> None:
        def explode(question: str, documents: tuple) -> dict:
            raise RuntimeError("model exploded")

        report = run(generate=explode)
        assert report["metrics"]["invalid_outputs"]["count"] == len(cases())
        assert report["metrics"]["invalid_outputs"]["total"] == len(cases())
        assert all(case["prediction_valid"] is False for case in report["cases"])
        assert all("generate_error" in case["error"] for case in report["cases"])


class TestAnswerKeyLeakage:
    def test_run_never_passes_evaluator_labels_to_generate(self) -> None:
        calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

        def generate(*args: Any, **kwargs: Any) -> dict[str, Any]:
            calls.append((args, kwargs))
            return _prediction(
                answer="insufficient evidence in the supplied sources",
                disposition="insufficient_evidence",
                evidence=[],
            )

        run(generate=generate)
        assert len(calls) == len(cases()), "every case must reach the generator"
        by_question = {case["question"]: case for case in cases()}
        for args, kwargs in calls:
            assert not _contains_evaluator_label(args), (
                "evaluation labels leaked as args"
            )
            assert not _contains_evaluator_label(kwargs), (
                "evaluation labels leaked as kwargs"
            )
            question = args[0] if args else kwargs.get("question")
            documents = args[1] if len(args) > 1 else kwargs.get("documents")
            case = by_question[question]
            authorized = {id(document) for document in case["authorized_documents"]}
            assert all(id(document) in authorized for document in documents), (
                f"a withheld document reached the generator for {case['id']}"
            )
