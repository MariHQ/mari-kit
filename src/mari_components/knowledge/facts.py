"""Fact extraction and evidence-based claim assessment."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from mari_components.errors import MalformedModelOutput
from mari_components.json import require_list
from mari_components.types import Evidence, FactCandidate, KnowledgeDocument

from .scoring import grounding_coverage

FACT_EXTRACTION_VERSION = "facts-extract-v2"
FACT_CHECK_VERSION = "facts-check-v2"


def _evidence(
    values: Any, allowed: Mapping[str, KnowledgeDocument], *, recipe: str
) -> tuple[Evidence, ...]:
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
            raise MalformedModelOutput(
                f"{recipe} evidence quote is not present in the document"
            )
        start = allowed[document_id].body.index(quote)
        output.append(
            Evidence(
                document_id=document_id,
                revision=allowed[document_id].revision,
                quote=quote,
                start=start,
                end=start + len(quote),
            )
        )
    return tuple(output)


def parse_facts(
    documents: Iterable[KnowledgeDocument],
    model_output: object,
) -> tuple[FactCandidate, ...]:
    allowed = {document.document_id: document for document in documents}
    rows = require_list(model_output, "facts", recipe=FACT_EXTRACTION_VERSION)
    output: list[FactCandidate] = []
    for row in rows:
        claim = str(row.get("claim") or "").strip()
        if not claim:
            raise MalformedModelOutput("fact claim is required")
        evidence = _evidence(
            row.get("evidence"), allowed, recipe=FACT_EXTRACTION_VERSION
        )
        output.append(
            FactCandidate(
                claim=claim,
                evidence=evidence,
                grounding_coverage=grounding_coverage(claim, evidence),
            )
        )
    return tuple(output)


@dataclass(frozen=True, slots=True)
class FactAssessment:
    claim: str
    verdict: str
    explanation: str
    grounding_coverage: float
    evidence: tuple[Evidence, ...]
    schema_version: str = FACT_CHECK_VERSION


def parse_claim_assessments(
    claims: Iterable[str],
    documents: Iterable[KnowledgeDocument],
    model_output: object,
) -> tuple[FactAssessment, ...]:
    selected_claims = tuple(
        str(claim).strip() for claim in claims if str(claim).strip()
    )
    allowed = {document.document_id: document for document in documents}
    rows = require_list(model_output, "assessments", recipe=FACT_CHECK_VERSION)
    if [str(row.get("claim") or "") for row in rows] != list(selected_claims):
        raise MalformedModelOutput(
            "fact check must return each input claim once and in order"
        )
    output: list[FactAssessment] = []
    for row in rows:
        verdict = str(row.get("verdict") or "")
        if verdict not in {"supported", "contradicted", "uncertain"}:
            raise MalformedModelOutput("fact verdict is invalid")
        evidence = (
            ()
            if verdict == "uncertain" and not row.get("evidence")
            else _evidence(row.get("evidence"), allowed, recipe=FACT_CHECK_VERSION)
        )
        claim = str(row["claim"])
        output.append(
            FactAssessment(
                claim,
                verdict,
                str(row.get("explanation") or ""),
                grounding_coverage(claim, evidence),
                evidence,
            )
        )
    return tuple(output)
