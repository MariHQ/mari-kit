"""Host-owned quality evaluation for the durable company brain wave-2 contract.

The evaluator grades whatever prediction a callback produced. It never contacts
a model itself: fixture mode uses a deterministic extractive baseline built on
Mari's revision BM25 index, and live mode is driven entirely by a caller-supplied
``generate(question, documents)`` callback.

Metrics are reported separately, each with an explicit denominator:

* citation validity: of the cases that expect a grounded answer, how many
  produced citations that resolve to authorized, current evidence;
* answer correctness proxy: of the cases that expect a grounded answer, how many
  produced text containing every required term and no forbidden term;
* abstention: how often the prediction abstained, and how often that matched the
  expectation;
* stale-answer rate: of grounded attempts, how many cited a superseded revision.

Invalid output is counted as failure in the disposition/abstention/citation
denominators and surfaced in ``invalid_outputs``; it never silently disappears.
The lexical term checks are a proxy: they cannot prove semantic correctness.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

from mari_kit.errors import MalformedModelOutput
from mari_kit.knowledge import parse_answer
from mari_kit.retrieval import RevisionBM25Index

from .quality_corpus import ABSTENTION_TEXT, build_prompt, cases

_TOKEN = re.compile(r"[a-z0-9]+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")

Generate = Callable[[str, tuple], dict]


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.casefold())


def _best_quote(body: str, question: str) -> str:
    """Return the sentence with the highest lexical overlap with the question."""

    sentences = [part.strip() for part in _SENTENCE.split(body.strip()) if part.strip()]
    if not sentences:
        return ""
    wanted = set(_tokens(question))
    return max(sentences, key=lambda row: len(wanted & set(_tokens(row))))


def default_generate(question: str, documents: tuple) -> dict:
    """Deterministic offline baseline used as the CI fixture callback."""

    docs = tuple(documents)
    if not docs:
        return {
            "answer": ABSTENTION_TEXT,
            "disposition": "insufficient_evidence",
            "evidence": [],
        }
    index = RevisionBM25Index({document.ref: document.body for document in docs})
    hits = index.search(question, limit=1)
    if not hits or hits[0].score <= 0:
        return {
            "answer": ABSTENTION_TEXT,
            "disposition": "insufficient_evidence",
            "evidence": [],
        }
    ref = hits[0].ref
    document = next(item for item in docs if item.ref == ref)
    quote = _best_quote(document.body, question)
    if not quote:
        return {
            "answer": ABSTENTION_TEXT,
            "disposition": "insufficient_evidence",
            "evidence": [],
        }
    return {
        "answer": quote,
        "disposition": "grounded",
        "evidence": [
            {
                "document_id": document.document_id,
                "revision": document.revision,
                "quote": quote,
            }
        ],
    }


def _raw_evidence(prediction: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(prediction, Mapping):
        return ()
    value = prediction.get("evidence")
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(row for row in value if isinstance(row, Mapping))


def _terms_match(text: str, required: list[str], forbidden: list[str]) -> bool:
    folded = text.casefold()
    return all(term.casefold() in folded for term in required) and not any(
        term.casefold() in folded for term in forbidden
    )


def evaluate_case(case: dict, prediction: dict) -> dict:
    """Grade one prediction against one case into separate observable metrics."""

    question = case["question"]
    expected = case["expected_disposition"]
    authorized = tuple(build_prompt(case)["documents"])
    current = {document.document_id: document.revision for document in authorized}
    corpus_ids = {document.document_id for document in case["documents"]}

    raw_disposition = ""
    if isinstance(prediction, Mapping):
        raw_disposition = str(prediction.get("disposition") or "").strip()
    rows = _raw_evidence(prediction)
    current_citations = stale_citations = unauthorized_citations = 0
    fabricated_citations = 0
    for row in rows:
        document_id = str(row.get("document_id") or "").strip()
        revision = str(row.get("revision") or "").strip()
        if document_id in current:
            if revision and revision != current[document_id]:
                stale_citations += 1
            else:
                current_citations += 1
        elif document_id in corpus_ids:
            unauthorized_citations += 1
        else:
            fabricated_citations += 1

    grounded_attempt = raw_disposition == "grounded"

    error = ""
    validated = None
    try:
        validated = parse_answer(question, authorized, prediction)
    except (MalformedModelOutput, ValueError, TypeError) as exc:
        error = f"{type(exc).__name__}: {exc}"

    valid = validated is not None
    disposition = validated.disposition.value if valid else ""
    grounded = bool(valid and disposition == "grounded")
    abstained = bool(valid and disposition == "insufficient_evidence")

    citation_valid = bool(
        grounded
        and current_citations >= 1
        and not stale_citations
        and not unauthorized_citations
        and not fabricated_citations
    )
    # A stale answer can omit a revision label. Keep this lexical signal
    # separate from the exact stale-citation count and disclose its limits.
    stale_content = bool(
        isinstance(prediction, Mapping)
        and "superseded" in case["category"]
        and any(
            term.casefold() in str(prediction.get("answer", "")).casefold()
            for term in case["forbidden_terms"]
        )
    )
    stale = bool(grounded_attempt and (stale_citations or stale_content))

    if expected == "grounded":
        answer_correct: bool | None = bool(
            grounded
            and _terms_match(
                validated.answer,
                list(case["required_terms"]),
                list(case["forbidden_terms"]),
            )
        )
    else:
        answer_correct = None

    return {
        "id": case["id"],
        "category": case["category"],
        "expected_disposition": expected,
        "predicted_disposition": raw_disposition,
        "prediction_valid": valid,
        "grounded": grounded,
        "grounded_attempt": grounded_attempt,
        "abstained": abstained,
        "expected_abstention": expected == "insufficient_evidence",
        "disposition_correct": bool(valid and disposition == expected),
        "evidence_count": len(rows),
        "current_citations": current_citations,
        "stale_citations": stale_citations,
        "stale_content_proxy": stale_content,
        "unauthorized_citations": unauthorized_citations,
        "fabricated_citations": fabricated_citations,
        "citation_valid": citation_valid,
        "stale": stale,
        "answer_correct": answer_correct,
        "error": error,
    }


def _by_category(results: list[dict]) -> dict[str, dict]:
    categories: dict[str, list[dict]] = {}
    for result in results:
        categories.setdefault(result["category"], []).append(result)
    summary: dict[str, dict] = {}
    for category, rows in sorted(categories.items()):
        expected_grounded = [
            row for row in rows if row["expected_disposition"] == "grounded"
        ]
        attempts = [row for row in rows if row["grounded_attempt"]]
        summary[category] = {
            "cases": len(rows),
            "invalid": sum(not row["prediction_valid"] for row in rows),
            "expected_grounded": len(expected_grounded),
            "citation_valid": sum(row["citation_valid"] for row in expected_grounded),
            "answer_correct": sum(
                bool(row["answer_correct"]) for row in expected_grounded
            ),
            "grounded_attempts": len(attempts),
            "stale": sum(row["stale"] for row in attempts),
            "abstained": sum(row["abstained"] for row in rows),
        }
    return summary


def summarize(results: list[dict]) -> dict:
    """Aggregate per-case metrics with explicit denominators."""

    total = len(results)
    invalid = sum(not row["prediction_valid"] for row in results)
    expected_grounded = [
        row for row in results if row["expected_disposition"] == "grounded"
    ]
    grounded_denominator = len(expected_grounded)
    citation_valid = sum(row["citation_valid"] for row in expected_grounded)
    answer_correct = sum(bool(row["answer_correct"]) for row in expected_grounded)
    disposition_correct = sum(row["disposition_correct"] for row in results)
    abstained = sum(row["abstained"] for row in results)
    abstention_correct = sum(
        row["abstained"] == row["expected_abstention"] for row in results
    )
    attempts = [row for row in results if row["grounded_attempt"]]
    stale = sum(row["stale"] for row in attempts)
    return {
        "case_count": total,
        "invalid_outputs": {
            "count": invalid,
            "total": total,
            "rate": _rate(invalid, total),
        },
        "citation_validity": {
            "valid": citation_valid,
            "total": grounded_denominator,
            "rate": _rate(citation_valid, grounded_denominator),
            "basis": "citation coverage of expected-grounded cases",
        },
        "emitted_citation_validity": {
            "valid": sum(row["citation_valid"] for row in attempts),
            "total": len(attempts),
            "rate": _rate(
                sum(row["citation_valid"] for row in attempts), len(attempts)
            ),
        },
        "answer_correctness_proxy": {
            "correct": answer_correct,
            "total": grounded_denominator,
            "rate": _rate(answer_correct, grounded_denominator),
        },
        "disposition_accuracy": {
            "correct": disposition_correct,
            "total": total,
            "rate": _rate(disposition_correct, total),
        },
        "abstention": {
            "abstained": abstained,
            "total": total,
            "rate": _rate(abstained, total),
            "expected": sum(row["expected_abstention"] for row in results),
            "correct_required_abstentions": sum(
                row["abstained"] and row["expected_abstention"] for row in results
            ),
            "unnecessary_abstentions": sum(
                row["abstained"] and not row["expected_abstention"] for row in results
            ),
            "accuracy": {
                "correct": abstention_correct,
                "total": total,
                "rate": _rate(abstention_correct, total),
            },
        },
        "stale": {
            "stale": stale,
            "total": len(attempts),
            "rate": _rate(stale, len(attempts)),
        },
        "by_category": _by_category(results),
    }


def run(generate: Generate | None = None) -> dict:
    """Evaluate the corpus in fixture mode or with a live callback.

    ``generate(question, documents)`` receives exactly the question and the
    authorized input documents from :func:`quality_corpus.build_prompt`. An
    exception from the callback is recorded as an invalid output rather than
    dropped, so it still counts in every denominator.
    """

    mode = "live" if generate is not None else "fixture"
    callback = generate if generate is not None else default_generate
    results: list[dict] = []
    for case in cases():
        prompt = build_prompt(case)
        generation_error = ""
        prediction: object = None
        try:
            prediction = callback(prompt["question"], prompt["documents"])
        except Exception as exc:  # noqa: BLE001 - a failed callback is an invalid output
            generation_error = f"generate_error: {type(exc).__name__}: {exc}"
        result = evaluate_case(case, prediction)
        if generation_error:
            result["error"] = generation_error
        results.append(result)
    return {"mode": mode, "metrics": summarize(results), "cases": results}


__all__ = ["default_generate", "evaluate_case", "run", "summarize"]


if __name__ == "__main__":
    import json

    print(json.dumps(run(), indent=2))
