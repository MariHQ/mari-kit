"""Content-addressed, passage-level planning for incremental fact extraction."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from mari_components.types import KnowledgeDocument, KnowledgeSection

from .sections import document_sections

FactScanRevisions = Mapping[tuple[str, str], str]


def pending_fact_sections(
    documents: Iterable[KnowledgeDocument],
    scanned_revisions: FactScanRevisions,
    *,
    query: str = "",
    limit: int = 50,
) -> tuple[KnowledgeSection, ...]:
    """Select unseen current sections fairly across documents.

    A section becomes pending when its content hash differs from its checkpoint.
    A non-empty query scopes work to sections containing that text. Selection is
    round-robin by section position so one long document cannot consume a bounded
    extraction run.

    Hosts should persist the returned section revisions only after extraction
    output and its review candidates have committed successfully, ideally in the
    same transaction.
    """
    if limit < 0:
        raise ValueError("fact scan limit cannot be negative")
    if limit == 0:
        return ()
    needle = str(query or "").strip().casefold()
    per_document: list[tuple[KnowledgeSection, ...]] = []
    for document in documents:
        pending = tuple(
            section
            for section in document_sections(document)
            if (not needle or needle in section.body.casefold())
            and scanned_revisions.get((section.document_id, section.section_id))
            != section.revision
        )
        if pending:
            per_document.append(pending)

    output: list[KnowledgeSection] = []
    passage_round = 0
    while len(output) < limit:
        added = False
        for sections in per_document:
            if passage_round < len(sections):
                output.append(sections[passage_round])
                added = True
                if len(output) == limit:
                    return tuple(output)
        if not added:
            break
        passage_round += 1
    return tuple(output)


def fact_scan_revisions(
    sections: Iterable[KnowledgeSection],
) -> dict[tuple[str, str], str]:
    """Build checkpoint updates for sections whose extraction committed."""
    return {
        (section.document_id, section.section_id): section.revision
        for section in sections
    }
