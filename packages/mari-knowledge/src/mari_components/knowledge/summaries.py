"""Digest summarization and evidence-linked impact assessment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from mari_components.errors import MalformedModelOutput
from mari_components.types import Evidence, KnowledgeDocument
from .facts import _evidence
from .prompting import JsonGenerator, bounded_documents, documents_json, require_object


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
    prompt_version: str = DIGEST_VERSION


@dataclass(frozen=True, slots=True)
class ImpactAssessment:
    summary: str
    affected_document_ids: tuple[str, ...]
    evidence: tuple[Evidence, ...]
    prompt_version: str = IMPACT_VERSION


def summarize_digest(documents: Iterable[KnowledgeDocument], *, generate_json: JsonGenerator, maximum_documents: int = 50, maximum_characters: int = 60_000) -> DigestSummary:
    bounded = bounded_documents(documents, maximum_documents=maximum_documents, maximum_characters=maximum_characters)
    allowed = {document.external_id: document for document in bounded}
    prompt = (
        "Summarize meaningful product-knowledge changes without inventing activity. Return concise topics and evidence. "
        'Return JSON {"summary":"...","topics":[{"title":"...","summary":"...",'
        '"evidence":[...]}],"evidence":[...]}.\nDocuments:\n' + documents_json(bounded)
    )
    value = require_object(generate_json(prompt, DIGEST_VERSION), recipe=DIGEST_VERSION)
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
        parsed.append(DigestTopic(title, summary, _evidence(topic.get("evidence"), allowed, recipe=DIGEST_VERSION)))
    if not parsed:
        raise MalformedModelOutput("at least one digest topic is required")
    return DigestSummary(str(value["summary"]).strip(), tuple(parsed), _evidence(value.get("evidence"), allowed, recipe=DIGEST_VERSION))


def assess_impact(changed_claim: str, documents: Iterable[KnowledgeDocument], *, generate_json: JsonGenerator, maximum_documents: int = 50, maximum_characters: int = 60_000) -> ImpactAssessment:
    bounded = bounded_documents(documents, maximum_documents=maximum_documents, maximum_characters=maximum_characters)
    allowed = {document.external_id: document for document in bounded}
    prompt = (
        "Assess which supplied documents are materially affected by the changed claim. Do not name documents outside the input. "
        'Return JSON {"summary":"...","affected_document_ids":["..."],"evidence":[...]}.\nChanged claim:\n'
        + changed_claim.strip() + "\nDocuments:\n" + documents_json(bounded)
    )
    value = require_object(generate_json(prompt, IMPACT_VERSION), recipe=IMPACT_VERSION)
    affected = value.get("affected_document_ids")
    if not str(value.get("summary") or "").strip() or not isinstance(affected, list):
        raise MalformedModelOutput("impact summary and affected document ids are required")
    ids = tuple(str(item) for item in affected)
    if any(item not in allowed for item in ids):
        raise MalformedModelOutput("impact assessment references an unknown document")
    evidence = () if not value.get("evidence") else _evidence(value.get("evidence"), allowed, recipe=IMPACT_VERSION)
    return ImpactAssessment(str(value["summary"]).strip(), ids, evidence)
