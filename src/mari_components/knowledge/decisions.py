"""Product decision extraction with source evidence."""

from __future__ import annotations

from collections.abc import Iterable

from mari_components.errors import MalformedModelOutput
from mari_components.json import require_list
from mari_components.types import DecisionCandidate, KnowledgeDocument

from .facts import _evidence
from .scoring import grounding_coverage

DECISION_VERSION = "decisions-extract-v2"


def parse_decisions(
    documents: Iterable[KnowledgeDocument],
    model_output: object,
) -> tuple[DecisionCandidate, ...]:
    allowed = {document.document_id: document for document in documents}
    rows = require_list(model_output, "decisions", recipe=DECISION_VERSION)
    output: list[DecisionCandidate] = []
    for row in rows:
        statement = str(row.get("statement") or "").strip()
        if not statement:
            raise MalformedModelOutput("decision statement is required")
        evidence = _evidence(row.get("evidence"), allowed, recipe=DECISION_VERSION)
        output.append(
            DecisionCandidate(
                statement=statement,
                evidence=evidence,
                grounding_coverage=grounding_coverage(statement, evidence),
            )
        )
    return tuple(output)
