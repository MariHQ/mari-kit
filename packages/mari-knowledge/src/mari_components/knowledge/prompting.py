"""Bounded prompt construction and strict provider-neutral JSON calls."""

from __future__ import annotations

import json
from typing import Iterable

from mari_components.json import JsonGenerator, require_list, require_object
from mari_components.types import KnowledgeDocument


def bounded_documents(
    documents: Iterable[KnowledgeDocument], *, maximum_documents: int, maximum_characters: int
) -> tuple[KnowledgeDocument, ...]:
    if maximum_documents < 1 or maximum_characters < 1:
        raise ValueError("document and character limits must be positive")
    output: list[KnowledgeDocument] = []
    used = 0
    for document in documents:
        if len(output) >= maximum_documents or used >= maximum_characters:
            break
        remaining = maximum_characters - used
        body = document.body[:remaining]
        output.append(
            KnowledgeDocument(
                document.external_id,
                document.title,
                body,
                document.revision,
                document.updated_at,
                document.source_url,
                document.acl,
                document.metadata,
            )
        )
        used += len(body)
    return tuple(output)


def documents_json(documents: Iterable[KnowledgeDocument]) -> str:
    return json.dumps(
        [
            {
                "document_id": document.external_id,
                "revision": document.revision,
                "title": document.title,
                "body": document.body,
            }
            for document in documents
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )


__all__ = [
    "JsonGenerator",
    "bounded_documents",
    "documents_json",
    "require_list",
    "require_object",
]
