"""Evidence requirements, context sufficiency, and retrieval-gap proposals."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from mari_components.errors import MalformedModelOutput
from mari_components.json import require_list

SUFFICIENCY_VERSION = "context-sufficiency-v1"


@dataclass(frozen=True, slots=True, kw_only=True)
class InformationRequirement:
    requirement_id: str
    description: str
    required: bool = True


class RequirementStatus(StrEnum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True, kw_only=True)
class RequirementAssessment:
    requirement_id: str
    status: RequirementStatus
    evidence_ids: tuple[str, ...] = ()
    explanation: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class SufficiencyReport:
    requirements: tuple[InformationRequirement, ...]
    assessments: tuple[RequirementAssessment, ...]
    missing_requirement_ids: tuple[str, ...]
    contradicted_requirement_ids: tuple[str, ...]
    ambiguous_requirement_ids: tuple[str, ...]
    required_coverage: float

    @property
    def sufficient(self) -> bool:
        return not (
            self.missing_requirement_ids
            or self.contradicted_requirement_ids
            or self.ambiguous_requirement_ids
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class RetrievalGapQuery:
    query: str
    requirement_ids: tuple[str, ...]
    rationale: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextUse:
    item_id: str
    token_count: int

    def __post_init__(self) -> None:
        if not self.item_id.strip() or self.token_count < 0:
            raise ValueError("context use requires an ID and non-negative token count")


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextContribution:
    selected_ids: tuple[str, ...]
    used_ids: tuple[str, ...]
    unused_ids: tuple[str, ...]
    selected_tokens: int
    used_tokens: int
    utilization: float
    observed_utility: float | None
    utility_per_thousand_tokens: float | None
    ablation_deltas: Mapping[str, float]


def parse_information_requirements(
    query: str, model_output: object
) -> tuple[InformationRequirement, ...]:
    """Validate a model-proposed decomposition without executing retrieval."""

    if not query.strip():
        raise ValueError("query is required")
    rows = require_list(model_output, "requirements", recipe=SUFFICIENCY_VERSION)
    output: list[InformationRequirement] = []
    seen: set[str] = set()
    for row in rows:
        description = str(row.get("description") or "").strip()[:500]
        if not description:
            raise MalformedModelOutput(
                "information requirement description is required"
            )
        identifier = str(row.get("id") or "").strip()[:100]
        if not identifier:
            digest = hashlib.sha256(description.casefold().encode()).hexdigest()[:16]
            identifier = f"requirement:{digest}"
        if identifier in seen:
            raise MalformedModelOutput("information requirement IDs must be unique")
        required = row.get("required", True)
        if not isinstance(required, bool):
            raise MalformedModelOutput(
                "information requirement required must be boolean"
            )
        output.append(
            InformationRequirement(
                requirement_id=identifier,
                description=description,
                required=required,
            )
        )
        seen.add(identifier)
    if not output:
        raise MalformedModelOutput("at least one information requirement is required")
    return tuple(output)


def assess_context_sufficiency(
    requirements: Iterable[InformationRequirement],
    assessments: Iterable[RequirementAssessment],
) -> SufficiencyReport:
    """Join requirement assessments and leave unassessed requirements missing."""

    required_values = tuple(requirements)
    if len({item.requirement_id for item in required_values}) != len(required_values):
        raise ValueError("requirement IDs must be unique")
    known = {item.requirement_id: item for item in required_values}
    by_id: dict[str, RequirementAssessment] = {}
    for item in assessments:
        if item.requirement_id not in known or item.requirement_id in by_id:
            raise ValueError("assessment requirement is unknown or repeated")
        if (
            item.status in {RequirementStatus.SUPPORTED, RequirementStatus.CONTRADICTED}
            and not item.evidence_ids
        ):
            raise ValueError("supported or contradicted assessments require evidence")
        by_id[item.requirement_id] = item
    completed = tuple(
        by_id.get(
            item.requirement_id,
            RequirementAssessment(
                requirement_id=item.requirement_id, status=RequirementStatus.MISSING
            ),
        )
        for item in required_values
    )
    required = {item.requirement_id for item in required_values if item.required}
    supported = {
        item.requirement_id
        for item in completed
        if item.status is RequirementStatus.SUPPORTED
    }
    return SufficiencyReport(
        requirements=required_values,
        assessments=completed,
        missing_requirement_ids=tuple(
            item.requirement_id
            for item in completed
            if item.status is RequirementStatus.MISSING
            and item.requirement_id in required
        ),
        contradicted_requirement_ids=tuple(
            item.requirement_id
            for item in completed
            if item.status is RequirementStatus.CONTRADICTED
            and item.requirement_id in required
        ),
        ambiguous_requirement_ids=tuple(
            item.requirement_id
            for item in completed
            if item.status is RequirementStatus.AMBIGUOUS
            and item.requirement_id in required
        ),
        required_coverage=len(required & supported) / len(required)
        if required
        else 1.0,
    )


def parse_retrieval_gap_queries(
    report: SufficiencyReport,
    model_output: object,
    *,
    maximum_queries: int = 4,
) -> tuple[RetrievalGapQuery, ...]:
    """Validate bounded follow-up query proposals against unresolved requirements."""

    if maximum_queries < 1:
        raise ValueError("maximum_queries must be positive")
    unresolved = set(report.missing_requirement_ids) | set(
        report.ambiguous_requirement_ids
    )
    rows = require_list(model_output, "queries", recipe=SUFFICIENCY_VERSION)
    if len(rows) > maximum_queries:
        raise MalformedModelOutput("too many retrieval gap queries")
    output: list[RetrievalGapQuery] = []
    for row in rows:
        query = str(row.get("query") or "").strip()[:500]
        raw_ids = row.get("requirement_ids")
        if not query or not isinstance(raw_ids, list) or not raw_ids:
            raise MalformedModelOutput("gap query and requirement IDs are required")
        ids = tuple(dict.fromkeys(str(item) for item in raw_ids))
        if set(ids) - unresolved:
            raise MalformedModelOutput("gap query references a resolved requirement")
        output.append(
            RetrievalGapQuery(
                query=query,
                requirement_ids=ids,
                rationale=str(row.get("rationale") or "")[:500],
            )
        )
    return tuple(output)


def evaluate_context_contribution(
    items: Iterable[ContextUse],
    *,
    used_ids: Iterable[str],
    observed_utility: float | None = None,
    ablated_utility: Mapping[str, float] | None = None,
) -> ContextContribution:
    """Account for observed use and caller-run ablations without causal claims."""

    values = tuple(items)
    if len({item.item_id for item in values}) != len(values):
        raise ValueError("context item IDs must be unique")
    selected = {item.item_id: item for item in values}
    used = set(used_ids)
    ablations = dict(ablated_utility or {})
    if used - selected.keys() or set(ablations) - selected.keys():
        raise ValueError("context use or ablation references an unknown item")
    if observed_utility is not None and not math.isfinite(observed_utility):
        raise ValueError("observed utility must be finite")
    if any(not math.isfinite(float(value)) for value in ablations.values()):
        raise ValueError("ablated utilities must be finite")
    total_tokens = sum(item.token_count for item in values)
    used_tokens = sum(selected[item].token_count for item in used)
    deltas = {
        item_id: observed_utility - float(value)
        for item_id, value in ablations.items()
        if observed_utility is not None
    }
    return ContextContribution(
        selected_ids=tuple(item.item_id for item in values),
        used_ids=tuple(sorted(used)),
        unused_ids=tuple(sorted(selected.keys() - used)),
        selected_tokens=total_tokens,
        used_tokens=used_tokens,
        utilization=used_tokens / total_tokens if total_tokens else 0.0,
        observed_utility=observed_utility,
        utility_per_thousand_tokens=(
            observed_utility * 1_000 / total_tokens
            if observed_utility is not None and total_tokens
            else None
        ),
        ablation_deltas=MappingProxyType(dict(sorted(deltas.items()))),
    )
