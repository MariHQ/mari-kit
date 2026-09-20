"""Shared validation of document collections consumed by evidence parsers.

Parsers resolve model citations against an allowance map keyed by
``KnowledgeDocument.document_id``. Building that map with a plain dict
comprehension silently keeps whichever document happens to be iterated last, so
two documents that share a ``document_id`` (a revised document, the same
provider identity in another tenant, or a malformed input) make citation
acceptance depend on argument order. This helper centralizes the defensive
check so every parser fails identically and unambiguously.
"""

from __future__ import annotations

from collections.abc import Iterable

from mari_kit.types import KnowledgeDocument


def document_lookup(
    documents: Iterable[KnowledgeDocument],
) -> dict[str, KnowledgeDocument]:
    """Index documents by ``document_id``, rejecting conflicting duplicates.

    Identical repeated documents (equal values) are collapsed and accepted, so
    passing the same document twice is harmless. Two distinct documents that
    share a ``document_id`` are ambiguous and raise :class:`ValueError` before
    any model output is parsed, which makes the failure independent of input
    order. This does not infer authorization: callers still supply only the
    documents the host has scoped to the operation.
    """
    allowed: dict[str, KnowledgeDocument] = {}
    for document in documents:
        previous = allowed.get(document.document_id)
        if previous is None:
            allowed[document.document_id] = document
        elif previous != document:
            raise ValueError(
                "conflicting documents share document_id "
                f"{document.document_id!r} (revisions {previous.revision!r} and "
                f"{document.revision!r}); provide one consistent document per "
                "document_id or namespace the documents"
            )
    return allowed
