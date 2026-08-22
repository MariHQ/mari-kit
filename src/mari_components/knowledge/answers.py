"""Grounded answer generation and reusable FAQ candidate mining."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from mari_components.errors import MalformedModelOutput
from mari_components.json import require_list, require_object
from mari_components.types import AnswerCandidate, Evidence, KnowledgeDocument

from .facts import _evidence
from .scoring import grounding_coverage

ANSWER_VERSION = "grounded-answer-v2"
FAQ_VERSION = "faq-mine-v2"


class AnswerDisposition(StrEnum):
    GROUNDED = "grounded"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True, slots=True, kw_only=True)
class GroundedAnswer:
    answer: str
    evidence: tuple[Evidence, ...]
    grounding_coverage: float
    disposition: AnswerDisposition
    schema_version: str = ANSWER_VERSION


def parse_answer(
    question: str,
    documents: Iterable[KnowledgeDocument],
    model_output: object,
) -> GroundedAnswer:
    question = question.strip()
    if not question:
        raise ValueError("question is required")
    allowed = {document.document_id: document for document in documents}
    value = require_object(model_output, recipe=ANSWER_VERSION)
    answer = str(value.get("answer") or "").strip()
    if not answer:
        raise MalformedModelOutput("grounded answer text is required")
    evidence = (
        ()
        if not value.get("evidence")
        else _evidence(value.get("evidence"), allowed, recipe=ANSWER_VERSION)
    )
    raw_disposition = str(
        value.get("disposition")
        or (
            AnswerDisposition.GROUNDED.value
            if evidence
            else AnswerDisposition.INSUFFICIENT_EVIDENCE.value
        )
    )
    try:
        disposition = AnswerDisposition(raw_disposition)
    except ValueError as error:
        raise MalformedModelOutput("grounded answer disposition is invalid") from error
    if disposition is AnswerDisposition.GROUNDED and not evidence:
        raise MalformedModelOutput("a grounded answer requires evidence")
    return GroundedAnswer(
        answer=answer,
        evidence=evidence,
        grounding_coverage=grounding_coverage(answer, evidence),
        disposition=disposition,
    )


def parse_answer_candidates(
    documents: Iterable[KnowledgeDocument],
    model_output: object,
) -> tuple[AnswerCandidate, ...]:
    allowed = {document.document_id: document for document in documents}
    rows = require_list(model_output, "answers", recipe=FAQ_VERSION)
    output: list[AnswerCandidate] = []
    for row in rows:
        question, answer = (
            str(row.get("question") or "").strip(),
            str(row.get("answer") or "").strip(),
        )
        if not question or not answer:
            raise MalformedModelOutput("FAQ question and answer are required")
        evidence = _evidence(row.get("evidence"), allowed, recipe=FAQ_VERSION)
        output.append(
            AnswerCandidate(
                question=question,
                answer=answer,
                evidence=evidence,
                grounding_coverage=grounding_coverage(answer, evidence),
            )
        )
    return tuple(output)
