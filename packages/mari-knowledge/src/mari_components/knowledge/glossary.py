"""Evidence-backed glossary harvesting."""

from __future__ import annotations

from typing import Iterable

from mari_components.errors import MalformedModelOutput
from mari_components.types import GlossaryCandidate, KnowledgeDocument
from .facts import _evidence
from .prompting import JsonGenerator, bounded_documents, documents_json, require_list


GLOSSARY_VERSION = "glossary-harvest-v1"


def harvest_glossary(documents: Iterable[KnowledgeDocument], *, generate_json: JsonGenerator, maximum_documents: int = 50, maximum_characters: int = 60_000) -> tuple[GlossaryCandidate, ...]:
    bounded = bounded_documents(documents, maximum_documents=maximum_documents, maximum_characters=maximum_characters)
    allowed = {document.external_id: document for document in bounded}
    prompt = (
        "Find organization-specific product terms that need a shared definition. Do not emit generic technology terms. "
        'Return JSON {"terms":[{"term":"...","definition":"...","aliases":["..."],"evidence":[...]}]}.\nDocuments:\n'
        + documents_json(bounded)
    )
    rows = require_list(generate_json(prompt, GLOSSARY_VERSION), "terms", recipe=GLOSSARY_VERSION)
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
        output.append(GlossaryCandidate(term, definition, _evidence(row.get("evidence"), allowed, recipe=GLOSSARY_VERSION), tuple(str(alias) for alias in aliases if str(alias).strip())))
    return tuple(output)
