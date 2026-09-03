"""Revision-bound contextual representations that preserve original source text."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np

from mari_components.errors import MalformedModelOutput
from mari_components.json import require_object
from mari_components.types import KnowledgeDocument, KnowledgeSection

CONTEXTUAL_REPRESENTATION_VERSION = "contextual-representation-v1"


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextualRepresentation:
    representation_id: str
    document_id: str
    section_id: str
    source_revision: str
    representation_revision: str
    original_text: str
    context_prefix: str
    indexing_text: str
    evidence_start: int
    evidence_end: int


def parse_chunk_context(
    document: KnowledgeDocument,
    section: KnowledgeSection,
    model_output: object,
    *,
    maximum_characters: int = 1_000,
) -> ContextualRepresentation:
    """Validate generated chunk context while retaining the exact source section."""

    if maximum_characters < 1:
        raise ValueError("maximum_characters must be positive")
    if section.document_id != document.document_id:
        raise ValueError("section belongs to another document")
    if document.body[section.start : section.end] != section.body:
        raise ValueError("section offsets do not match the document revision")
    value = require_object(model_output, recipe=CONTEXTUAL_REPRESENTATION_VERSION)
    prefix = str(value.get("context") or "").strip()
    if not prefix or len(prefix) > maximum_characters:
        raise MalformedModelOutput("chunk context is empty or exceeds its bound")
    representation_revision = hashlib.sha256(
        f"{section.revision}\0{prefix}".encode()
    ).hexdigest()
    return ContextualRepresentation(
        representation_id=f"{section.document_id}#{section.section_id}@{representation_revision[:16]}",
        document_id=section.document_id,
        section_id=section.section_id,
        source_revision=section.revision,
        representation_revision=representation_revision,
        original_text=section.body,
        context_prefix=prefix,
        indexing_text=f"{prefix}\n\n{section.body}",
        evidence_start=section.start,
        evidence_end=section.end,
    )


def contextual_representation(
    section: KnowledgeSection, context: str
) -> ContextualRepresentation:
    """Create a representation when context was produced by deterministic code."""

    prefix = context.strip()
    if not prefix:
        raise ValueError("context is required")
    revision = hashlib.sha256(f"{section.revision}\0{prefix}".encode()).hexdigest()
    return ContextualRepresentation(
        representation_id=f"{section.document_id}#{section.section_id}@{revision[:16]}",
        document_id=section.document_id,
        section_id=section.section_id,
        source_revision=section.revision,
        representation_revision=revision,
        original_text=section.body,
        context_prefix=prefix,
        indexing_text=f"{prefix}\n\n{section.body}",
        evidence_start=section.start,
        evidence_end=section.end,
    )


def pool_token_spans(
    token_embeddings: Sequence[Sequence[float]],
    spans: Iterable[tuple[int, int]],
) -> tuple[tuple[float, ...], ...]:
    """Mean-pool half-open token spans for late-chunking style representations."""

    matrix = np.asarray(token_embeddings, dtype=np.float64)
    if matrix.ndim != 2 or not matrix.shape[0] or not matrix.shape[1]:
        raise ValueError("token embeddings must be a non-empty matrix")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("token embeddings must be finite")
    output: list[tuple[float, ...]] = []
    for start, end in spans:
        if start < 0 or end <= start or end > len(matrix):
            raise ValueError("token span is outside the embedding sequence")
        output.append(
            tuple(float(value) for value in np.mean(matrix[start:end], axis=0))
        )
    return tuple(output)
