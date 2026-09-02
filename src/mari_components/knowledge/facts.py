"""Fact extraction and evidence-based claim assessment."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from mari_components.errors import MalformedModelOutput
from mari_components.json import require_list
from mari_components.types import Evidence, FactCandidate, KnowledgeDocument

from .scoring import grounding_coverage
from .sections import document_sections

FACT_EXTRACTION_VERSION = "facts-extract-v3"
FACT_CHECK_VERSION = "facts-check-v2"


def normalize_claim(claim: str) -> str:
    """Return a conservative identity for case, spacing, and punctuation variants."""
    folded = unicodedata.normalize("NFKC", str(claim)).casefold()
    return " ".join(re.sub(r"[\W_]+", " ", folded, flags=re.UNICODE).split())


def _evidence(
    values: Any, allowed: Mapping[str, KnowledgeDocument], *, recipe: str
) -> tuple[Evidence, ...]:
    if not isinstance(values, list) or not values:
        raise MalformedModelOutput(f"{recipe} evidence must be a non-empty array")
    output: list[Evidence] = []
    for value in values:
        if isinstance(value, str):
            quote = value.strip()
            holders = [
                document_id
                for document_id, document in allowed.items()
                if quote and quote in document.body
            ]
            value = (
                {"document_id": holders[0], "quote": quote}
                if len(holders) == 1
                else {"quote": quote}
            )
        if not isinstance(value, dict):
            raise MalformedModelOutput(f"{recipe} evidence entries must be objects")
        document_id = str(value.get("document_id") or "")
        quote = str(value.get("quote") or "").strip()
        if document_id not in allowed and quote and len(allowed) == 1:
            only_id, only_document = next(iter(allowed.items()))
            if quote in only_document.body:
                document_id = only_id
        if document_id not in allowed:
            raise MalformedModelOutput(f"{recipe} references an unknown document")
        if not quote:
            raise MalformedModelOutput(f"{recipe} evidence quote is required")
        document = allowed[document_id]
        if quote not in document.body:
            raise MalformedModelOutput(
                f"{recipe} evidence quote is not present in the document"
            )
        requested_section = str(value.get("section_id") or "").strip()
        sections = document_sections(document)
        matching_sections = [
            section
            for section in sections
            if quote in section.body
            and (not requested_section or section.section_id == requested_section)
        ]
        if not matching_sections:
            raise MalformedModelOutput(
                f"{recipe} evidence quote is not present in the requested section"
            )
        if len(matching_sections) > 1:
            raise MalformedModelOutput(
                f"{recipe} repeated evidence quote requires section_id"
            )
        section = matching_sections[0]
        start = section.start + section.body.index(quote)
        output.append(
            Evidence(
                document_id=document_id,
                revision=document.revision,
                quote=quote,
                start=start,
                end=start + len(quote),
                section_id=section.section_id,
                section_revision=section.revision,
            )
        )
    return tuple(output)


def parse_facts(
    documents: Iterable[KnowledgeDocument],
    model_output: object,
) -> tuple[FactCandidate, ...]:
    """Validate evidence-linked atomic facts proposed from documents.

    The task shape follows atomic factual decomposition (FActScore,
    arXiv:2305.14251) and document-level relation extraction (DocRED,
    arXiv:1906.06127). Mari validates supplied rows; it does not run those
    models or claim their benchmark behavior.
    """
    allowed = {document.document_id: document for document in documents}
    rows = require_list(model_output, "facts", recipe=FACT_EXTRACTION_VERSION)
    output: list[FactCandidate] = []
    seen: set[str] = set()
    for row in rows:
        claim = str(row.get("claim") or "").strip()
        if not claim:
            raise MalformedModelOutput("fact claim is required")
        claim_key = normalize_claim(claim)
        if not claim_key or claim_key in seen:
            continue
        evidence = _evidence(
            row.get("evidence"), allowed, recipe=FACT_EXTRACTION_VERSION
        )
        qualifiers = {
            key: row.get(key)
            for key in (
                "atomic_claims",
                "subject",
                "relation",
                "object",
                "scopes",
                "valid_from",
                "valid_to",
                "conditions",
            )
            if key in row
        }
        output.append(
            FactCandidate(
                claim=claim,
                evidence=evidence,
                grounding_coverage=grounding_coverage(claim, evidence),
                qualifiers=qualifiers,
            )
        )
        seen.add(claim_key)
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
    """Validate supported/contradicted/uncertain judgments and their evidence.

    The three-way evidence-bearing task follows FEVER (arXiv:1803.05355).
    Mari conservatively maps missing or unverifiable evidence to ``uncertain``.
    """
    selected_claims = tuple(
        str(claim).strip() for claim in claims if str(claim).strip()
    )
    allowed = {document.document_id: document for document in documents}
    rows = require_list(model_output, "assessments", recipe=FACT_CHECK_VERSION)
    matched = _match_assessments(selected_claims, rows)
    if selected_claims and not any(row is not None for row in matched):
        raise MalformedModelOutput("fact check did not address any input claim")
    output: list[FactAssessment] = []
    for claim, row in zip(selected_claims, matched, strict=True):
        if row is None:
            output.append(
                FactAssessment(
                    claim,
                    "uncertain",
                    "The model did not address this claim.",
                    0.0,
                    (),
                )
            )
            continue
        verdict = str(row.get("verdict") or "")
        if verdict not in {"supported", "contradicted", "uncertain"}:
            raise MalformedModelOutput("fact verdict is invalid")
        explanation = str(row.get("explanation") or "")
        if verdict == "uncertain" and not row.get("evidence"):
            evidence: tuple[Evidence, ...] = ()
        else:
            try:
                evidence = _evidence(
                    row.get("evidence"), allowed, recipe=FACT_CHECK_VERSION
                )
            except MalformedModelOutput:
                verdict = "uncertain"
                evidence = ()
                explanation = (
                    f"{explanation} " if explanation else ""
                ) + "(The cited evidence could not be verified against the document.)"
        output.append(
            FactAssessment(
                claim,
                verdict,
                explanation,
                grounding_coverage(claim, evidence),
                evidence,
            )
        )
    return tuple(output)


def deduplicate_fact_candidates(
    candidates: Iterable[FactCandidate], *, existing_claims: Iterable[str] = ()
) -> tuple[FactCandidate, ...]:
    """Keep the first candidate for each normalized claim not already stored."""
    seen = {normalize_claim(claim) for claim in existing_claims}
    output: list[FactCandidate] = []
    for candidate in candidates:
        key = normalize_claim(candidate.claim)
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(candidate)
    return tuple(output)


def _match_assessments(
    claims: tuple[str, ...], rows: list[Mapping[str, Any]]
) -> tuple[Mapping[str, Any] | None, ...]:
    """Match reordered, lightly paraphrased model rows without losing input identity."""
    remaining = list(rows)
    matched: list[Mapping[str, Any] | None] = []
    for claim in claims:
        hit = next(
            (row for row in remaining if str(row.get("claim") or "") == claim), None
        )
        wanted = normalize_claim(claim)
        if hit is None:
            hit = next(
                (
                    row
                    for row in remaining
                    if normalize_claim(str(row.get("claim") or "")) == wanted
                ),
                None,
            )
        if hit is None:
            best: Mapping[str, Any] | None = None
            best_ratio = 0.0
            for row in remaining:
                ratio = SequenceMatcher(
                    None,
                    wanted,
                    normalize_claim(str(row.get("claim") or "")),
                ).ratio()
                if ratio > best_ratio:
                    best, best_ratio = row, ratio
            hit = best if best_ratio >= 0.85 else None
        matched.append(hit)
        if hit is not None:
            remaining.remove(hit)
    return tuple(matched)
