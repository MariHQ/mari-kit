"""Deterministic Markdown sections for fine-grained knowledge dependencies."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping

from mari_components.types import KnowledgeDocument, KnowledgeSection

_HEADING = re.compile(r"(?m)^(#{1,6})[ \t]+(.+?)[ \t]*$")
_SLUG_CHARACTER = re.compile(r"[^a-z0-9]+")


def _slug(value: str) -> str:
    return _SLUG_CHARACTER.sub("-", value.casefold()).strip("-") or "section"


def _revision(body: str) -> str:
    return hashlib.sha256(body.encode()).hexdigest()


def document_sections(document: KnowledgeDocument) -> tuple[KnowledgeSection, ...]:
    """Split Markdown by heading path and hash each section's exact source text.

    Heading paths remain stable when unrelated sections move or change. Duplicate
    paths receive deterministic occurrence suffixes. Text before the first
    heading is represented as ``preamble``; a heading-free document is ``root``.
    """
    matches = tuple(_HEADING.finditer(document.body))
    if not matches:
        return (
            KnowledgeSection(
                document_id=document.document_id,
                section_id="root",
                title=document.title,
                body=document.body,
                revision=_revision(document.body),
                start=0,
                end=len(document.body),
            ),
        )
    output: list[KnowledgeSection] = []
    if matches[0].start() > 0:
        body = document.body[: matches[0].start()]
        output.append(
            KnowledgeSection(
                document_id=document.document_id,
                section_id="preamble",
                title=document.title,
                body=body,
                revision=_revision(body),
                start=0,
                end=matches[0].start(),
            )
        )
    path: list[str] = []
    occurrences: dict[str, int] = {}
    for index, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()
        path = path[: level - 1]
        path.append(_slug(title))
        raw_id = "/".join(path)
        occurrences[raw_id] = occurrences.get(raw_id, 0) + 1
        occurrence = occurrences[raw_id]
        section_id = raw_id if occurrence == 1 else f"{raw_id}-{occurrence}"
        start = match.start()
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(document.body)
        )
        body = document.body[start:end]
        output.append(
            KnowledgeSection(
                document_id=document.document_id,
                section_id=section_id,
                title=title,
                body=body,
                revision=_revision(body),
                start=start,
                end=end,
            )
        )
    return tuple(output)


def section_revisions(
    documents: Iterable[KnowledgeDocument],
) -> Mapping[tuple[str, str], str]:
    """Return the current section revisions expected by freshness policies."""
    return {
        (section.document_id, section.section_id): section.revision
        for document in documents
        for section in document_sections(document)
    }
