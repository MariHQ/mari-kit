"""Digest summarization and evidence-linked impact assessment."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from mari_components.errors import MalformedModelOutput
from mari_components.json import require_object
from mari_components.types import Evidence, KnowledgeDocument

from .facts import _evidence

DIGEST_VERSION = "digest-summary-v1"
IMPACT_VERSION = "impact-assessment-v1"


@dataclass(frozen=True, slots=True)
class DigestTopic:
    title: str
    summary: str
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class DigestSummary:
    summary: str
    topics: tuple[DigestTopic, ...]
    evidence: tuple[Evidence, ...]
    schema_version: str = DIGEST_VERSION


@dataclass(frozen=True, slots=True)
class ImpactAssessment:
    summary: str
    affected_document_ids: tuple[str, ...]
    evidence: tuple[Evidence, ...]
    schema_version: str = IMPACT_VERSION


def parse_digest(
    documents: Iterable[KnowledgeDocument],
    model_output: object,
) -> DigestSummary:
    """Validate an evidence-linked overall and topic-level digest.

    QAGS (arXiv:2004.04228) and SummaC (arXiv:2111.09525) motivate treating
    summary consistency as separate from fluency. Mari resolves citations but
    does not treat exact quotation as proof of semantic entailment.
    """
    allowed = {document.document_id: document for document in documents}
    value = require_object(model_output, recipe=DIGEST_VERSION)
    topics = value.get("topics")
    if not str(value.get("summary") or "").strip() or not isinstance(topics, list):
        raise MalformedModelOutput("digest summary and topics are required")
    parsed: list[DigestTopic] = []
    for topic in topics:
        if not isinstance(topic, dict):
            raise MalformedModelOutput("each digest topic must be an object")
        title = str(topic.get("title") or "").strip()
        summary = str(topic.get("summary") or "").strip()
        if not title or not summary:
            raise MalformedModelOutput("digest topic title and summary are required")
        parsed.append(
            DigestTopic(
                title,
                summary,
                _evidence(topic.get("evidence"), allowed, recipe=DIGEST_VERSION),
            )
        )
    if not parsed:
        raise MalformedModelOutput("at least one digest topic is required")
    return DigestSummary(
        str(value["summary"]).strip(),
        tuple(parsed),
        _evidence(value.get("evidence"), allowed, recipe=DIGEST_VERSION),
    )


def parse_impact(
    documents: Iterable[KnowledgeDocument],
    model_output: object,
) -> ImpactAssessment:
    """Validate an in-scope, optionally evidenced change-impact proposal."""
    allowed = {document.document_id: document for document in documents}
    value = require_object(model_output, recipe=IMPACT_VERSION)
    affected = value.get("affected_document_ids")
    if not str(value.get("summary") or "").strip() or not isinstance(affected, list):
        raise MalformedModelOutput(
            "impact summary and affected document ids are required"
        )
    ids = tuple(str(item) for item in affected)
    if any(item not in allowed for item in ids):
        raise MalformedModelOutput("impact assessment references an unknown document")
    evidence = (
        ()
        if not value.get("evidence")
        else _evidence(value.get("evidence"), allowed, recipe=IMPACT_VERSION)
    )
    return ImpactAssessment(str(value["summary"]).strip(), ids, evidence)
