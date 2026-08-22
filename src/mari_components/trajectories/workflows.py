"""Match reviewed intents and safely reuse their knowledge dependencies."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import TypeVar

import numpy as np

from mari_components.knowledge import (
    FreshnessReport,
    GroundedAnswer,
    assess_dependencies,
)
from mari_components.retrieval import MuveraIndex, build_index, search_index


@dataclass(frozen=True, slots=True, kw_only=True)
class ReviewedWorkflow:
    """A human-approved intent and read-only fast path learned from trajectories.

    This is the portable equivalent of Mari Cloud's assistant workflow record.
    It is guidance and a reviewed-answer cache, not an agent runtime or
    executable workflow engine.
    """

    identifier: str
    name: str
    match_vectors: tuple[tuple[float, ...], ...]
    document_ids: tuple[str, ...]
    cached_answer: GroundedAnswer | None = None

    def __post_init__(self) -> None:
        matrix = np.asarray(self.match_vectors, np.float32)
        if not self.identifier.strip() or not self.name.strip():
            raise ValueError("workflow identifier and name are required")
        if matrix.ndim != 2 or not len(matrix) or not np.all(np.isfinite(matrix)):
            raise ValueError("workflow match vectors must be a finite matrix")
        if not self.document_ids or len(set(self.document_ids)) != len(
            self.document_ids
        ):
            raise ValueError("workflow document IDs must be non-empty and unique")
        if self.cached_answer is not None and not {
            row.document_id for row in self.cached_answer.knowledge_dependencies
        }.issubset(self.document_ids):
            raise ValueError(
                "cached answer dependencies must refer to workflow documents"
            )
        if self.cached_answer is not None and not self.cached_answer.evidence:
            raise ValueError("cached answers must contain grounded evidence")


@dataclass(frozen=True, slots=True)
class ReviewedWorkflowMatch:
    workflow: ReviewedWorkflow
    score: float


@dataclass(frozen=True, slots=True)
class ReviewedWorkflowIndex:
    workflows: Mapping[str, ReviewedWorkflow]
    muvera: MuveraIndex

    def __post_init__(self) -> None:
        object.__setattr__(self, "workflows", MappingProxyType(dict(self.workflows)))


class CacheDecisionReason(StrEnum):
    HIT = "hit"
    BELOW_THRESHOLD = "below_threshold"
    NO_CACHED_RESPONSE = "no_cached_response"
    STALE_DEPENDENCY = "stale_dependency"


class WorkflowAction(StrEnum):
    CACHED_RESPONSE = "cached_response"
    SPECULATIVE_RETRIEVAL = "speculative_retrieval"
    LLM = "llm"


class WorkflowDecisionReason(StrEnum):
    EXACT_FRESH_CACHE = "exact_fresh_cache"
    NO_INTENT_MATCH = "no_intent_match"
    NO_CACHED_RESPONSE = "no_cached_response"
    STALE_DEPENDENCY = "stale_dependency"
    RELEVANT_DOCUMENT_NEEDS_IMPACT_REVIEW = "relevant_document_needs_impact_review"
    RELEVANT_DOCUMENT_IMPACTS_RESPONSE = "relevant_document_impacts_response"
    BELOW_CACHE_THRESHOLD = "below_cache_threshold"


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkflowPolicy:
    """Conservative policy for reviewed intent reuse.

    ``cache_threshold`` is intentionally higher: cached prose is returned only
    for an extremely close intent match. A lower ``speculation_threshold`` may
    launch read-only document retrieval while the host agent continues.
    """

    speculation_threshold: float = 0.70
    cache_threshold: float = 0.97
    relevant_document_threshold: float = 0.85

    def __post_init__(self) -> None:
        values = (
            self.speculation_threshold,
            self.cache_threshold,
            self.relevant_document_threshold,
        )
        if any(not -1 <= value <= 1 for value in values):
            raise ValueError("workflow thresholds must be between -1 and 1")
        if self.cache_threshold < self.speculation_threshold:
            raise ValueError("cache_threshold must be at least speculation_threshold")


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkflowDecision:
    action: WorkflowAction
    reason: WorkflowDecisionReason
    match: ReviewedWorkflowMatch | None = None
    document_ids: tuple[str, ...] = ()
    documents_needing_impact_review: tuple[str, ...] = ()

    @property
    def cached_answer(self) -> GroundedAnswer | None:
        if self.action is WorkflowAction.CACHED_RESPONSE and self.match is not None:
            return self.match.workflow.cached_answer
        return None


@dataclass(frozen=True, slots=True, kw_only=True)
class CacheDecision:
    reason: CacheDecisionReason
    threshold: float
    match: ReviewedWorkflowMatch | None = None
    freshness: FreshnessReport | None = None

    @property
    def reusable(self) -> bool:
        return self.reason is CacheDecisionReason.HIT and self.match is not None


def build_reviewed_workflow_index(
    workflows: Iterable[ReviewedWorkflow],
) -> ReviewedWorkflowIndex:
    """Build one immutable MUVERA index for repeated intent and cache lookups."""
    values = tuple(workflows)
    by_id = {row.identifier: row for row in values}
    if not values or len(by_id) != len(values):
        raise ValueError("reviewed workflows must be non-empty with unique identifiers")
    muvera = build_index(
        {row.identifier: np.asarray(row.match_vectors, np.float32) for row in values}
    )
    return ReviewedWorkflowIndex(by_id, muvera)


def match_reviewed_workflow(
    query_vectors: Sequence[Sequence[float]],
    index: ReviewedWorkflowIndex,
    *,
    minimum_score: float,
    allowed_document_ids: Collection[str] | None = None,
) -> ReviewedWorkflowMatch | None:
    """Match against a reusable reviewed-intent MUVERA index."""
    if not -1 <= minimum_score <= 1:
        raise ValueError("minimum_score must be between -1 and 1")
    allowed_workflows = None
    if allowed_document_ids is not None:
        allowed = frozenset(str(value) for value in allowed_document_ids)
        allowed_workflows = {
            identifier
            for identifier, workflow in index.workflows.items()
            if set(workflow.document_ids).issubset(allowed)
        }
        if not allowed_workflows:
            return None
    hits = search_index(
        index.muvera,
        np.asarray(query_vectors, np.float32),
        limit=1,
        allowed_document_ids=allowed_workflows,
    )
    if not hits:
        return None
    hit = hits[0]
    if hit.score < minimum_score:
        return None
    return ReviewedWorkflowMatch(index.workflows[hit.document_id], hit.score)


def workflow_freshness(
    workflow: ReviewedWorkflow,
    current_revisions: Mapping[str, str],
    *,
    current_section_revisions: Mapping[tuple[str, str], str] | None = None,
) -> FreshnessReport:
    dependencies = (
        workflow.cached_answer.knowledge_dependencies if workflow.cached_answer else ()
    )
    return assess_dependencies(
        dependencies,
        current_revisions,
        current_section_revisions=current_section_revisions,
    )


def match_cached_response(
    query_vectors: Sequence[Sequence[float]],
    index: ReviewedWorkflowIndex,
    current_revisions: Mapping[str, str],
    *,
    minimum_score: float,
    current_section_revisions: Mapping[tuple[str, str], str] | None = None,
    allowed_document_ids: Collection[str] | None = None,
) -> CacheDecision:
    """Select the highest-scoring fresh cached response and explain every miss."""
    if not -1 <= minimum_score <= 1:
        raise ValueError("minimum_score must be between -1 and 1")
    allowed_workflows = None
    visible_workflows = tuple(index.workflows.values())
    if allowed_document_ids is not None:
        allowed = frozenset(str(value) for value in allowed_document_ids)
        allowed_workflows = {
            identifier
            for identifier, workflow in index.workflows.items()
            if set(workflow.document_ids).issubset(allowed)
        }
        visible_workflows = tuple(
            index.workflows[identifier] for identifier in allowed_workflows
        )
    hits = search_index(
        index.muvera,
        np.asarray(query_vectors, np.float32),
        limit=len(index.workflows),
        candidate_limit=len(index.workflows),
        allowed_document_ids=allowed_workflows,
    )
    stale_report: FreshnessReport | None = None
    for hit in hits:
        if hit.score < minimum_score:
            break
        workflow = index.workflows[hit.document_id]
        if workflow.cached_answer is None:
            continue
        freshness = workflow_freshness(
            workflow,
            current_revisions,
            current_section_revisions=current_section_revisions,
        )
        if freshness.reusable:
            return CacheDecision(
                reason=CacheDecisionReason.HIT,
                threshold=minimum_score,
                match=ReviewedWorkflowMatch(workflow, hit.score),
                freshness=freshness,
            )
        stale_report = stale_report or freshness
    if stale_report is not None:
        return CacheDecision(
            reason=CacheDecisionReason.STALE_DEPENDENCY,
            threshold=minimum_score,
            freshness=stale_report,
        )
    return CacheDecision(
        reason=(
            CacheDecisionReason.NO_CACHED_RESPONSE
            if not any(row.cached_answer is not None for row in visible_workflows)
            else CacheDecisionReason.BELOW_THRESHOLD
        ),
        threshold=minimum_score,
    )


def decide_reviewed_workflow(
    query_vectors: Sequence[Sequence[float]],
    index: ReviewedWorkflowIndex,
    current_revisions: Mapping[str, str],
    *,
    current_section_revisions: Mapping[tuple[str, str], str] | None = None,
    allowed_document_ids: Collection[str] | None = None,
    relevant_document_scores: Mapping[str, float] | None = None,
    impact_decisions: Mapping[str, bool] | None = None,
    policy: WorkflowPolicy | None = None,
) -> WorkflowDecision:
    """Choose cache reuse, actual speculative reads, or the host LLM.

    ``impact_decisions[document_id]`` is ``True`` when a user has determined a
    newly relevant document affects the answer and ``False`` when it does not.
    Unreviewed highly relevant documents conservatively force the LLM path.
    """
    selected_policy = policy or WorkflowPolicy()
    relevant_scores = relevant_document_scores or {}
    decisions = impact_decisions or {}
    match = match_reviewed_workflow(
        query_vectors,
        index,
        minimum_score=selected_policy.speculation_threshold,
        allowed_document_ids=allowed_document_ids,
    )
    if match is None:
        return WorkflowDecision(
            action=WorkflowAction.LLM,
            reason=WorkflowDecisionReason.NO_INTENT_MATCH,
        )
    workflow = match.workflow
    allowed = (
        None
        if allowed_document_ids is None
        else frozenset(str(value) for value in allowed_document_ids)
    )
    relevant = tuple(
        sorted(
            document_id
            for document_id, score in relevant_scores.items()
            if score >= selected_policy.relevant_document_threshold
            and document_id not in workflow.document_ids
            and (allowed is None or document_id in allowed)
        )
    )
    unresolved = tuple(row for row in relevant if row not in decisions)
    impactful = tuple(row for row in relevant if decisions.get(row) is True)
    selected_ids = tuple(dict.fromkeys((*workflow.document_ids, *relevant)))
    freshness = workflow_freshness(
        workflow,
        current_revisions,
        current_section_revisions=current_section_revisions,
    )
    if unresolved:
        return WorkflowDecision(
            action=WorkflowAction.SPECULATIVE_RETRIEVAL,
            reason=WorkflowDecisionReason.RELEVANT_DOCUMENT_NEEDS_IMPACT_REVIEW,
            match=match,
            document_ids=selected_ids,
            documents_needing_impact_review=unresolved,
        )
    if impactful:
        return WorkflowDecision(
            action=WorkflowAction.SPECULATIVE_RETRIEVAL,
            reason=WorkflowDecisionReason.RELEVANT_DOCUMENT_IMPACTS_RESPONSE,
            match=match,
            document_ids=selected_ids,
        )
    if not freshness.reusable:
        return WorkflowDecision(
            action=WorkflowAction.SPECULATIVE_RETRIEVAL,
            reason=WorkflowDecisionReason.STALE_DEPENDENCY,
            match=match,
            document_ids=selected_ids,
        )
    if workflow.cached_answer is None:
        return WorkflowDecision(
            action=WorkflowAction.SPECULATIVE_RETRIEVAL,
            reason=WorkflowDecisionReason.NO_CACHED_RESPONSE,
            match=match,
            document_ids=selected_ids,
        )
    if match.score < selected_policy.cache_threshold:
        return WorkflowDecision(
            action=WorkflowAction.SPECULATIVE_RETRIEVAL,
            reason=WorkflowDecisionReason.BELOW_CACHE_THRESHOLD,
            match=match,
            document_ids=selected_ids,
        )
    return WorkflowDecision(
        action=WorkflowAction.CACHED_RESPONSE,
        reason=WorkflowDecisionReason.EXACT_FRESH_CACHE,
        match=match,
        document_ids=selected_ids,
    )


T = TypeVar("T")


def start_speculative_retrieval(
    decision: WorkflowDecision,
    retrieve_documents: Callable[[tuple[str, ...]], Awaitable[T]],
) -> asyncio.Task[T]:
    """Launch the reviewed read before the host agent chooses its tool call.

    This is deliberately not an agent loop. The returned standard asyncio task
    can be awaited, cancelled, or handed to an agent-framework tool adapter.
    """
    if decision.action is not WorkflowAction.SPECULATIVE_RETRIEVAL:
        raise ValueError("decision does not permit speculative retrieval")

    async def invoke() -> T:
        return await retrieve_documents(decision.document_ids)

    return asyncio.create_task(invoke())
