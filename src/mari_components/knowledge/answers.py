"""Grounded answer generation and reusable FAQ candidate mining."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from mari_components.errors import MalformedModelOutput
from mari_components.json import require_list, require_object
from mari_components.types import AnswerCandidate, Evidence, KnowledgeDocument

from .facts import _evidence
from .freshness import KnowledgeDependency, evidence_dependencies
from .scoring import grounding_coverage

ANSWER_VERSION = "grounded-answer-v3"
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
    context_dependencies: tuple[KnowledgeDependency, ...] = ()
    schema_version: str = ANSWER_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(
            self, "context_dependencies", tuple(self.context_dependencies)
        )
        if not self.answer.strip():
            raise ValueError("grounded answer text is required")
        if not isinstance(self.disposition, AnswerDisposition):
            raise TypeError("answer disposition must be an AnswerDisposition")
        if self.disposition is AnswerDisposition.GROUNDED and not self.evidence:
            raise ValueError("a grounded answer requires evidence")
        if (
            not math.isfinite(self.grounding_coverage)
            or not 0 <= self.grounding_coverage <= 1
        ):
            raise ValueError("grounding coverage must be between zero and one")
        evidence_keys = {
            (row.document_id, row.section_id)
            for row in evidence_dependencies(self.evidence)
        }
        context_keys = {
            (row.document_id, row.section_id) for row in self.context_dependencies
        }
        if len(context_keys) != len(self.context_dependencies):
            raise ValueError("answer context dependencies must be unique")
        if evidence_keys.intersection(context_keys):
            raise ValueError("answer dependencies must be unique")

    @property
    def knowledge_dependencies(self) -> tuple[KnowledgeDependency, ...]:
        return (*evidence_dependencies(self.evidence), *self.context_dependencies)


def parse_answer(
    question: str,
    documents: Iterable[KnowledgeDocument],
    model_output: object,
    *,
    context_dependencies: Iterable[KnowledgeDependency] = (),
) -> GroundedAnswer:
    """Validate an evidence-grounded answer or explicit abstention.

    The contract is informed by evidence-selected document QA in QASPER
    (arXiv:2105.03011) and citation evaluation in ALCE (arXiv:2305.14627).
    """
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
        context_dependencies=tuple(context_dependencies),
    )


def parse_answer_candidates(
    documents: Iterable[KnowledgeDocument],
    model_output: object,
) -> tuple[AnswerCandidate, ...]:
    """Validate reusable question-answer candidates with exact source evidence."""
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
