"""Fact extraction and evidence-based claim assessment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from mari_components.errors import MalformedModelOutput
from mari_components.types import Evidence, FactCandidate, KnowledgeDocument
from .prompting import JsonGenerator, bounded_documents, documents_json, require_list
from .scoring import evidence_confidence


FACT_EXTRACTION_VERSION = "facts-extract-v2"
FACT_CHECK_VERSION = "facts-check-v2"


def _evidence(values: Any, allowed: Mapping[str, KnowledgeDocument], *, recipe: str) -> tuple[Evidence, ...]:
    if not isinstance(values, list) or not values:
        raise MalformedModelOutput(f"{recipe} evidence must be a non-empty array")
    output: list[Evidence] = []
    for value in values:
        if not isinstance(value, dict):
            raise MalformedModelOutput(f"{recipe} evidence entries must be objects")
        document_id = str(value.get("document_id") or "")
        if document_id not in allowed:
            raise MalformedModelOutput(f"{recipe} references an unknown document")
        quote = str(value.get("quote") or "").strip()
        if not quote:
            raise MalformedModelOutput(f"{recipe} evidence quote is required")
        if quote not in allowed[document_id].body:
            raise MalformedModelOutput(f"{recipe} evidence quote is not present in the document")
        output.append(Evidence(document_id, allowed[document_id].revision, quote))
    return tuple(output)


def extract_facts(
    documents: Iterable[KnowledgeDocument], *, generate_json: JsonGenerator,
    maximum_documents: int = 50, maximum_characters: int = 60_000,
) -> tuple[FactCandidate, ...]:
    bounded = bounded_documents(documents, maximum_documents=maximum_documents, maximum_characters=maximum_characters)
    allowed = {document.external_id: document for document in bounded}
    prompt = (
        "Extract durable, atomic product facts from the supplied documents. "
        "Do not infer beyond the text. Every fact must cite at least one exact document id and quote. "
        'Return JSON {"facts":[{"claim":"...",'
        '"evidence":[{"document_id":"...","quote":"..."}]}]}.\nDocuments:\n'
        + documents_json(bounded)
    )
    rows = require_list(generate_json(prompt, FACT_EXTRACTION_VERSION), "facts", recipe=FACT_EXTRACTION_VERSION)
    output: list[FactCandidate] = []
    for row in rows:
        claim = str(row.get("claim") or "").strip()
        if not claim:
            raise MalformedModelOutput("fact claim is required")
        evidence = _evidence(row.get("evidence"), allowed, recipe=FACT_EXTRACTION_VERSION)
        output.append(FactCandidate(claim, evidence, evidence_confidence(claim, evidence)))
    return tuple(output)


@dataclass(frozen=True, slots=True)
class FactAssessment:
    claim: str
    verdict: str
    explanation: str
    confidence: float
    evidence: tuple[Evidence, ...]
    prompt_version: str = FACT_CHECK_VERSION


def check_claims(
    claims: Iterable[str], documents: Iterable[KnowledgeDocument], *, generate_json: JsonGenerator,
    maximum_claims: int = 50, maximum_documents: int = 50, maximum_characters: int = 60_000,
) -> tuple[FactAssessment, ...]:
    selected_claims = tuple(str(claim).strip() for claim in claims if str(claim).strip())[:maximum_claims]
    bounded = bounded_documents(documents, maximum_documents=maximum_documents, maximum_characters=maximum_characters)
    allowed = {document.external_id: document for document in bounded}
    prompt = (
        "Assess each supplied claim only against the evidence. Verdict must be supported, contradicted, or uncertain. "
        "Preserve every claim exactly and cite evidence for supported or contradicted results. "
        'Return JSON {"assessments":[{"claim":"...","verdict":"supported|contradicted|uncertain",'
        '"explanation":"...","evidence":[...]}]}.\nClaims:\n'
        + "\n".join(f"- {claim}" for claim in selected_claims)
        + "\nDocuments:\n" + documents_json(bounded)
    )
    rows = require_list(generate_json(prompt, FACT_CHECK_VERSION), "assessments", recipe=FACT_CHECK_VERSION)
    if [str(row.get("claim") or "") for row in rows] != list(selected_claims):
        raise MalformedModelOutput("fact check must return each input claim once and in order")
    output: list[FactAssessment] = []
    for row in rows:
        verdict = str(row.get("verdict") or "")
        if verdict not in {"supported", "contradicted", "uncertain"}:
            raise MalformedModelOutput("fact verdict is invalid")
        evidence = () if verdict == "uncertain" and not row.get("evidence") else _evidence(row.get("evidence"), allowed, recipe=FACT_CHECK_VERSION)
        claim = str(row["claim"])
        output.append(FactAssessment(
            claim, verdict, str(row.get("explanation") or ""),
            evidence_confidence(claim, evidence), evidence,
        ))
    return tuple(output)
