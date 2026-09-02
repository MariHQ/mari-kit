"""Bounded, exact-substring document refinement proposals."""

from __future__ import annotations

from dataclasses import dataclass

from mari_components.errors import MalformedModelOutput
from mari_components.json import require_object
from mari_components.types import KnowledgeDocument

REFINEMENT_VERSION = "document-refinement-v1"


@dataclass(frozen=True, slots=True)
class RefinementEdit:
    original: str
    replacement: str
    reason: str
    schema_version: str = REFINEMENT_VERSION


def parse_refinement(
    document: KnowledgeDocument,
    model_output: object,
    *,
    maximum_edits: int = 4,
) -> tuple[RefinementEdit, ...]:
    """Validate bounded exact-substring revision proposals.

    Attribution-aware and fact-based revision are studied by RARR
    (arXiv:2210.08726) and FactEditor (arXiv:2007.00916). Mari returns edits for
    review and never applies them to the source document.
    """
    if maximum_edits < 1:
        raise ValueError("maximum_edits must be positive")
    body = document.body[:60_000]
    value = require_object(model_output, recipe=REFINEMENT_VERSION)
    raw = value.get("edits")
    if not isinstance(raw, list):
        raise MalformedModelOutput("document refinement edits are required")
    output: list[RefinementEdit] = []
    seen: set[str] = set()
    for item in raw[:maximum_edits]:
        if not isinstance(item, dict):
            raise MalformedModelOutput(
                "each document refinement edit must be an object"
            )
        original = str(item.get("original") or "").strip()
        replacement = str(item.get("replacement") or "").strip()
        reason = str(item.get("reason") or "").strip()
        if not original or original not in body:
            raise MalformedModelOutput(
                "a refinement original is not present in the document"
            )
        if not replacement or replacement == original or not reason:
            raise MalformedModelOutput("refinement replacement and reason are required")
        if original in seen:
            continue
        seen.add(original)
        output.append(RefinementEdit(original, replacement, reason))
    return tuple(output)
