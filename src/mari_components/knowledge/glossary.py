"""Evidence-backed glossary harvesting."""

from __future__ import annotations

from collections.abc import Iterable

from mari_components.errors import MalformedModelOutput
from mari_components.json import require_list
from mari_components.types import GlossaryCandidate, KnowledgeDocument

from .facts import _evidence

GLOSSARY_VERSION = "glossary-harvest-v1"


def parse_glossary(
    documents: Iterable[KnowledgeDocument],
    model_output: object,
) -> tuple[GlossaryCandidate, ...]:
    allowed = {document.document_id: document for document in documents}
    rows = require_list(model_output, "terms", recipe=GLOSSARY_VERSION)
    output: list[GlossaryCandidate] = []
    seen: set[str] = set()
    for row in rows:
        term = str(row.get("term") or "").strip()
        definition = str(row.get("definition") or "").strip()
        if not term or not definition or term.casefold() in seen:
            if term.casefold() in seen:
                continue
            raise MalformedModelOutput("glossary term and definition are required")
        aliases = row.get("aliases") or []
        if not isinstance(aliases, list):
            raise MalformedModelOutput("glossary aliases must be an array")
        seen.add(term.casefold())
        output.append(
            GlossaryCandidate(
                term=term,
                definition=definition,
                evidence=_evidence(
                    row.get("evidence"), allowed, recipe=GLOSSARY_VERSION
                ),
                aliases=tuple(str(alias) for alias in aliases if str(alias).strip()),
            )
        )
    return tuple(output)
