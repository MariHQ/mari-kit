"""Grounded answer generation and reusable FAQ candidate mining."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from mari_components.errors import MalformedModelOutput
from mari_components.types import AnswerCandidate, Evidence, KnowledgeDocument
from .facts import _evidence
from .prompting import JsonGenerator, bounded_documents, documents_json, require_list, require_object
from .scoring import evidence_confidence


ANSWER_VERSION = "grounded-answer-v2"
FAQ_VERSION = "faq-mine-v2"


@dataclass(frozen=True, slots=True)
class GroundedAnswer:
    answer: str
    evidence: tuple[Evidence, ...]
    confidence: float
    prompt_version: str = ANSWER_VERSION


def answer_question(question: str, documents: Iterable[KnowledgeDocument], *, generate_json: JsonGenerator, maximum_documents: int = 20, maximum_characters: int = 40_000) -> GroundedAnswer:
    question = question.strip()
    if not question:
        raise ValueError("question is required")
    bounded = bounded_documents(documents, maximum_documents=maximum_documents, maximum_characters=maximum_characters)
    allowed = {document.external_id: document for document in bounded}
    prompt = (
        "Answer only from the supplied product knowledge. Say that the evidence is insufficient when necessary. "
        "Cite exact document ids and quotes. "
        'Return JSON {"answer":"...","evidence":[...]}.\nQuestion:\n'
        + question + "\nDocuments:\n" + documents_json(bounded)
    )
    value = require_object(generate_json(prompt, ANSWER_VERSION), recipe=ANSWER_VERSION)
    answer = str(value.get("answer") or "").strip()
    if not answer:
        raise MalformedModelOutput("grounded answer text is required")
    evidence = () if not value.get("evidence") else _evidence(value.get("evidence"), allowed, recipe=ANSWER_VERSION)
    return GroundedAnswer(answer, evidence, evidence_confidence(answer, evidence))


def mine_answers(documents: Iterable[KnowledgeDocument], *, generate_json: JsonGenerator, maximum_documents: int = 50, maximum_characters: int = 60_000) -> tuple[AnswerCandidate, ...]:
    bounded = bounded_documents(documents, maximum_documents=maximum_documents, maximum_characters=maximum_characters)
    allowed = {document.external_id: document for document in bounded}
    prompt = (
        "Mine recurring product questions that the documents answer directly. Each answer must be independently useful and evidenced. "
        'Return JSON {"answers":[{"question":"...","answer":"...","evidence":[...]}]}.\nDocuments:\n'
        + documents_json(bounded)
    )
    rows = require_list(generate_json(prompt, FAQ_VERSION), "answers", recipe=FAQ_VERSION)
    output: list[AnswerCandidate] = []
    for row in rows:
        question, answer = str(row.get("question") or "").strip(), str(row.get("answer") or "").strip()
        if not question or not answer:
            raise MalformedModelOutput("FAQ question and answer are required")
        evidence = _evidence(row.get("evidence"), allowed, recipe=FAQ_VERSION)
        output.append(AnswerCandidate(
            question, answer, evidence, evidence_confidence(answer, evidence),
        ))
    return tuple(output)
