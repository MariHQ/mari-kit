"""Bounded, exact-substring document refinement proposals."""

from __future__ import annotations

from dataclasses import dataclass

from mari_components.errors import MalformedModelOutput
from mari_components.types import KnowledgeDocument
from .prompting import JsonGenerator, require_object


REFINEMENT_VERSION = "document-refinement-v1"


@dataclass(frozen=True, slots=True)
class RefinementEdit:
    original: str
    replacement: str
    reason: str
    prompt_version: str = REFINEMENT_VERSION


def refine_document(
    document: KnowledgeDocument,
    instruction: str,
    *,
    generate_json: JsonGenerator,
    maximum_edits: int = 4,
) -> tuple[RefinementEdit, ...]:
    if maximum_edits < 1:
        raise ValueError("maximum_edits must be positive")
    body = document.body[:60_000]
    prompt = (
        "Propose only localized edits that follow the instruction. Every original must be an exact, "
        "non-empty substring of the supplied document. Do not rewrite the whole document. "
        'Return JSON {"edits":[{"original":"...","replacement":"...","reason":"..."}]} '
        f"with at most {maximum_edits} edits.\nInstruction:\n{instruction.strip()}\n"
        f"Document title:\n{document.title}\nDocument body:\n{body}"
    )
    value = require_object(generate_json(prompt, REFINEMENT_VERSION), recipe=REFINEMENT_VERSION)
    raw = value.get("edits")
    if not isinstance(raw, list):
        raise MalformedModelOutput("document refinement edits are required")
    output: list[RefinementEdit] = []
    seen: set[str] = set()
    for item in raw[:maximum_edits]:
        if not isinstance(item, dict):
            raise MalformedModelOutput("each document refinement edit must be an object")
        original = str(item.get("original") or "").strip()
        replacement = str(item.get("replacement") or "").strip()
        reason = str(item.get("reason") or "").strip()
        if not original or original not in body:
            raise MalformedModelOutput("a refinement original is not present in the document")
        if not replacement or replacement == original or not reason:
            raise MalformedModelOutput("refinement replacement and reason are required")
        if original in seen:
            continue
        seen.add(original)
        output.append(RefinementEdit(original, replacement, reason))
    return tuple(output)
