"""Match reviewed intents and safely reuse their knowledge dependencies."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import TypeVar

import numpy as np

from mari_components.knowledge import FreshnessReport, assess_freshness
from mari_components.retrieval import MuveraIndex, build_index, search_index
from mari_components.types import Evidence


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
    cache_dependencies: Mapping[str, str] = field(default_factory=dict)
    cached_answer: str = ""

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
        if set(self.cache_dependencies) - set(self.document_ids):
            raise ValueError("cache dependencies must refer to workflow documents")
        object.__setattr__(
            self, "cache_dependencies", MappingProxyType(dict(self.cache_dependencies))
        )


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
    def cached_answer(self) -> str:
        if self.action is WorkflowAction.CACHED_RESPONSE and self.match is not None:
            return self.match.workflow.cached_answer
        return ""


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
) -> ReviewedWorkflowMatch | None:
    """Match against a reusable reviewed-intent MUVERA index."""
    if not -1 <= minimum_score <= 1:
        raise ValueError("minimum_score must be between -1 and 1")
    hit = search_index(index.muvera, np.asarray(query_vectors, np.float32), limit=1)[0]
    if hit.score < minimum_score:
        return None
    return ReviewedWorkflowMatch(index.workflows[hit.document_id], hit.score)


def workflow_freshness(
    workflow: ReviewedWorkflow,
    current_revisions: Mapping[str, str],
) -> FreshnessReport:
    evidence = tuple(
        Evidence(document_id=document_id, revision=revision)
        for document_id, revision in workflow.cache_dependencies.items()
    )
    return assess_freshness(evidence, current_revisions)


def match_cached_response(
    query_vectors: Sequence[Sequence[float]],
    index: ReviewedWorkflowIndex,
    current_revisions: Mapping[str, str],
    *,
    minimum_score: float,
) -> CacheDecision:
    """Select the highest-scoring fresh cached response and explain every miss."""
    if not -1 <= minimum_score <= 1:
        raise ValueError("minimum_score must be between -1 and 1")
    hits = search_index(
        index.muvera,
        np.asarray(query_vectors, np.float32),
        limit=len(index.workflows),
        candidate_limit=len(index.workflows),
    )
    stale_report: FreshnessReport | None = None
    for hit in hits:
        if hit.score < minimum_score:
            break
        workflow = index.workflows[hit.document_id]
        if not workflow.cached_answer or not workflow.cache_dependencies:
            continue
        freshness = workflow_freshness(workflow, current_revisions)
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
            if not any(
                row.cached_answer and row.cache_dependencies
                for row in index.workflows.values()
            )
            else CacheDecisionReason.BELOW_THRESHOLD
        ),
        threshold=minimum_score,
    )


def impacted_workflows(
    workflows: Iterable[ReviewedWorkflow],
    current_revisions: Mapping[str, str],
) -> tuple[str, ...]:
    """Return reviewed caches made stale by changed or removed documents."""
    return tuple(
        sorted(
            row.identifier
            for row in workflows
            if row.cache_dependencies
            and not workflow_freshness(row, current_revisions).reusable
        )
    )


def decide_reviewed_workflow(
    query_vectors: Sequence[Sequence[float]],
    index: ReviewedWorkflowIndex,
    current_revisions: Mapping[str, str],
    *,
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
    )
    if match is None:
        return WorkflowDecision(
            action=WorkflowAction.LLM,
            reason=WorkflowDecisionReason.NO_INTENT_MATCH,
        )
    workflow = match.workflow
    relevant = tuple(
        sorted(
            document_id
            for document_id, score in relevant_scores.items()
            if score >= selected_policy.relevant_document_threshold
            and document_id not in workflow.document_ids
        )
    )
    unresolved = tuple(row for row in relevant if row not in decisions)
    impactful = tuple(row for row in relevant if decisions.get(row) is True)
    selected_ids = tuple(dict.fromkeys((*workflow.document_ids, *relevant)))
    freshness = workflow_freshness(workflow, current_revisions)
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
    if not workflow.cached_answer or not workflow.cache_dependencies:
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
