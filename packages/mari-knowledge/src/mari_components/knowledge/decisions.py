"""Product decision extraction with source evidence."""

from __future__ import annotations

from typing import Iterable

from mari_components.errors import MalformedModelOutput
from mari_components.types import DecisionCandidate, KnowledgeDocument
from .facts import _evidence
from .prompting import JsonGenerator, bounded_documents, documents_json, require_list
from .scoring import evidence_confidence


DECISION_VERSION = "decisions-extract-v2"


def extract_decisions(documents: Iterable[KnowledgeDocument], *, generate_json: JsonGenerator, maximum_documents: int = 50, maximum_characters: int = 60_000) -> tuple[DecisionCandidate, ...]:
    bounded = bounded_documents(documents, maximum_documents=maximum_documents, maximum_characters=maximum_characters)
    allowed = {document.external_id: document for document in bounded}
    prompt = (
        "Extract explicit product or engineering decisions, not suggestions. Preserve evidence. "
        'Return JSON {"decisions":[{"statement":"...","evidence":[{"document_id":"...","quote":"..."}]}]}.\nDocuments:\n'
        + documents_json(bounded)
    )
    rows = require_list(generate_json(prompt, DECISION_VERSION), "decisions", recipe=DECISION_VERSION)
    output: list[DecisionCandidate] = []
    for row in rows:
        statement = str(row.get("statement") or "").strip()
        if not statement:
            raise MalformedModelOutput("decision statement is required")
        evidence = _evidence(row.get("evidence"), allowed, recipe=DECISION_VERSION)
        output.append(DecisionCandidate(
            statement, evidence, evidence_confidence(statement, evidence),
        ))
    return tuple(output)
