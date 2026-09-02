"""Model-neutral execution boundaries derived from retrieval research.

The host supplies model-dependent embeddings, summaries, relevance judgments,
and token probabilities. This module validates and deterministically executes
the reusable planning and selection steps.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy import typing as npt

FloatArray = npt.NDArray[np.floating]


def hypothetical_document_embedding(
    embeddings: Sequence[FloatArray],
    *,
    weights: Sequence[float] | None = None,
) -> npt.NDArray[np.float32]:
    """Return the normalized HyDE retrieval vector for hypothetical documents.

    HyDE generates text outside this function. Callers embed that text and pass
    one or more vectors here; multiple hypotheses are combined by a weighted
    centroid before L2 normalization.

    Source: Gao et al., "Precise Zero-Shot Dense Retrieval without Relevance
    Labels" (arXiv:2212.10496).
    """
    if not embeddings:
        raise ValueError("at least one hypothetical embedding is required")
    arrays = [np.asarray(value, dtype=np.float64) for value in embeddings]
    shape = arrays[0].shape
    if len(shape) != 1 or shape[0] == 0:
        raise ValueError("hypothetical embeddings must be non-empty vectors")
    if any(value.shape != shape for value in arrays):
        raise ValueError("hypothetical embeddings must have equal dimensions")
    if any(not np.all(np.isfinite(value)) for value in arrays):
        raise ValueError("hypothetical embeddings must be finite")

    raw_weights = [1.0] * len(arrays) if weights is None else list(weights)
    if len(raw_weights) != len(arrays):
        raise ValueError("weights must match the number of embeddings")
    weight_array = np.asarray(raw_weights, dtype=np.float64)
    if not np.all(np.isfinite(weight_array)) or np.any(weight_array <= 0):
        raise ValueError("weights must be positive finite numbers")
    centroid = np.average(np.stack(arrays), axis=0, weights=weight_array)
    norm = float(np.linalg.norm(centroid))
    if norm == 0:
        raise ValueError("the hypothetical embedding centroid must be non-zero")
    return np.asarray(centroid / norm, dtype=np.float32)


@dataclass(frozen=True, slots=True, kw_only=True)
class SummaryTreeNode:
    """One leaf or recursively summarized RAPTOR tree node."""

    node_id: str
    text: str
    level: int
    children: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class SummaryTree:
    """A complete immutable tree plus its current roots."""

    nodes: tuple[SummaryTreeNode, ...]
    root_ids: tuple[str, ...]


def build_summary_tree(
    leaves: Mapping[str, str],
    *,
    cluster: Callable[[tuple[SummaryTreeNode, ...], int], Iterable[Iterable[str]]],
    summarize: Callable[[tuple[SummaryTreeNode, ...], int], str],
    max_levels: int = 8,
) -> SummaryTree:
    """Recursively cluster and summarize nodes using RAPTOR's tree structure.

    The callbacks own embedding, clustering, and model calls. Every clustering
    level must partition all current roots exactly once and reduce their count.

    Source: Sarthi et al., "RAPTOR" (arXiv:2401.18059).
    """
    if not leaves:
        raise ValueError("at least one leaf is required")
    if max_levels < 1:
        raise ValueError("max_levels must be positive")
    if any(not str(node_id) or not str(text) for node_id, text in leaves.items()):
        raise ValueError("leaf IDs and text must not be empty")

    known: dict[str, SummaryTreeNode] = {
        str(node_id): SummaryTreeNode(node_id=str(node_id), text=str(text), level=0)
        for node_id, text in sorted(leaves.items())
    }
    current = tuple(known[node_id] for node_id in sorted(known))
    for level in range(1, max_levels + 1):
        if len(current) == 1:
            break
        groups = [tuple(str(node_id) for node_id in group) for group in cluster(current, level)]
        if not groups or any(not group for group in groups):
            raise ValueError("clusters must be non-empty")
        flattened = [node_id for group in groups for node_id in group]
        current_ids = {node.node_id for node in current}
        if len(flattened) != len(set(flattened)) or set(flattened) != current_ids:
            raise ValueError("clusters must partition every current node exactly once")
        if len(groups) >= len(current):
            raise ValueError("each summary level must reduce the number of roots")

        parents: list[SummaryTreeNode] = []
        for group in groups:
            children = tuple(known[node_id] for node_id in group)
            text = str(summarize(children, level)).strip()
            if not text:
                raise ValueError("summaries must not be empty")
            digest = hashlib.sha256("\0".join(sorted(group)).encode()).hexdigest()[:16]
            node_id = f"summary:{level}:{digest}"
            parent = SummaryTreeNode(
                node_id=node_id,
                text=text,
                level=level,
                children=tuple(group),
            )
            known[node_id] = parent
            parents.append(parent)
        current = tuple(sorted(parents, key=lambda node: node.node_id))
    return SummaryTree(
        nodes=tuple(sorted(known.values(), key=lambda node: (node.level, node.node_id))),
        root_ids=tuple(node.node_id for node in current),
    )


class CorrectiveAction(StrEnum):
    """CRAG action selected from retrieval confidence."""

    USE_RETRIEVED = "use_retrieved"
    COMBINE_WITH_EXTERNAL = "combine_with_external"
    REPLACE_WITH_EXTERNAL = "replace_with_external"


@dataclass(frozen=True, slots=True, kw_only=True)
class CorrectiveRetrievalPlan:
    """Auditable CRAG threshold decision."""

    action: CorrectiveAction
    confidence: float
    lower_threshold: float
    upper_threshold: float


def plan_corrective_retrieval(
    relevance_scores: Iterable[float],
    *,
    lower_threshold: float = 0.3,
    upper_threshold: float = 0.7,
) -> CorrectiveRetrievalPlan:
    """Map the best document relevance score to a CRAG retrieval action.

    Source: Yan et al., "Corrective Retrieval Augmented Generation"
    (arXiv:2401.15884).
    """
    scores = tuple(float(value) for value in relevance_scores)
    if not scores:
        raise ValueError("at least one relevance score is required")
    if any(not math.isfinite(value) for value in scores):
        raise ValueError("relevance scores must be finite")
    if (
        not math.isfinite(lower_threshold)
        or not math.isfinite(upper_threshold)
        or lower_threshold >= upper_threshold
    ):
        raise ValueError("thresholds must be finite and satisfy lower < upper")
    confidence = max(scores)
    if confidence >= upper_threshold:
        action = CorrectiveAction.USE_RETRIEVED
    elif confidence <= lower_threshold:
        action = CorrectiveAction.REPLACE_WITH_EXTERNAL
    else:
        action = CorrectiveAction.COMBINE_WITH_EXTERNAL
    return CorrectiveRetrievalPlan(
        action=action,
        confidence=confidence,
        lower_threshold=lower_threshold,
        upper_threshold=upper_threshold,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class ActiveRetrievalQuery:
    """A FLARE query derived from one low-confidence future sentence."""

    query: str
    low_confidence_positions: tuple[int, ...]
    confidence: float


def plan_active_retrieval(
    tokens: Sequence[str],
    probabilities: Sequence[float],
    *,
    threshold: float = 0.2,
) -> ActiveRetrievalQuery | None:
    """Create FLARE's masked retrieval query when a token is low confidence.

    Low-confidence tokens are removed from the predicted sentence. The caller
    owns next-sentence generation and regeneration after retrieval.

    Source: Jiang et al., "Active Retrieval Augmented Generation"
    (arXiv:2305.06983).
    """
    if len(tokens) != len(probabilities):
        raise ValueError("tokens and probabilities must have equal lengths")
    if not tokens:
        raise ValueError("at least one token is required")
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("threshold must be a finite value in [0, 1]")
    values = tuple(float(value) for value in probabilities)
    if any(not math.isfinite(value) or not 0 <= value <= 1 for value in values):
        raise ValueError("probabilities must be finite values in [0, 1]")
    positions = tuple(index for index, value in enumerate(values) if value < threshold)
    if not positions:
        return None
    query = " ".join(
        str(token).strip()
        for index, token in enumerate(tokens)
        if index not in positions and str(token).strip()
    )
    return ActiveRetrievalQuery(
        query=query,
        low_confidence_positions=positions,
        confidence=min(values),
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class TreeWalk:
    """Trace and selected leaves from bounded MemWalker-style navigation."""

    visited: tuple[str, ...]
    leaf_ids: tuple[str, ...]
    exhausted: bool


def walk_summary_tree(
    tree: SummaryTree,
    score: Callable[[SummaryTreeNode], float],
    *,
    branch_factor: int = 1,
    max_visits: int = 32,
) -> TreeWalk:
    """Navigate summary nodes toward the most relevant leaves with a trace.

    The caller supplies query-to-summary scoring. At each visited internal node,
    only its highest-scoring children are expanded.

    Source: Chen et al., "Walking Down the Memory Maze" (arXiv:2310.05029).
    """
    if branch_factor < 1 or max_visits < 1:
        raise ValueError("branch_factor and max_visits must be positive")
    nodes = {node.node_id: node for node in tree.nodes}
    if len(nodes) != len(tree.nodes):
        raise ValueError("tree node IDs must be unique")
    if any(root not in nodes for root in tree.root_ids):
        raise ValueError("tree roots must reference known nodes")

    frontier = list(tree.root_ids)
    visited: list[str] = []
    leaves: list[str] = []
    while frontier and len(visited) < max_visits:
        node_id = frontier.pop(0)
        node = nodes[node_id]
        visited.append(node_id)
        if not node.children:
            leaves.append(node_id)
            continue
        if any(child not in nodes for child in node.children):
            raise ValueError("tree children must reference known nodes")
        scored: list[tuple[float, str]] = []
        for child_id in node.children:
            value = float(score(nodes[child_id]))
            if not math.isfinite(value):
                raise ValueError("tree relevance scores must be finite")
            scored.append((value, child_id))
        chosen = [node_id for _, node_id in sorted(scored, key=lambda row: (-row[0], row[1]))[:branch_factor]]
        frontier[0:0] = chosen
    return TreeWalk(
        visited=tuple(visited),
        leaf_ids=tuple(leaves),
        exhausted=not frontier,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class CompressionSentence:
    """A source sentence considered by a RECOMP extractive compressor."""

    sentence_id: str
    text: str
    token_count: int
    relevance: float


@dataclass(frozen=True, slots=True, kw_only=True)
class CompressionResult:
    """Selected source-order sentences and the selection trace."""

    text: str
    selected_ids: tuple[str, ...]
    excluded_ids: tuple[str, ...]
    token_count: int


def selective_compression(
    sentences: Sequence[CompressionSentence],
    *,
    token_budget: int,
    relevance_threshold: float = 0.0,
) -> CompressionResult:
    """Select externally scored sentences under a budget, or return empty text.

    Candidates are greedily admitted by relevance per token and rendered in
    original source order. This is the deterministic executor around RECOMP's
    learned extractive scores, not its model implementation.

    Source: Xu, Shi, and Choi, "RECOMP" (arXiv:2310.04408).
    """
    if token_budget < 0:
        raise ValueError("token_budget must not be negative")
    if not math.isfinite(relevance_threshold):
        raise ValueError("relevance_threshold must be finite")
    ids = [sentence.sentence_id for sentence in sentences]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("sentence IDs must be non-empty and unique")
    if any(sentence.token_count < 1 for sentence in sentences):
        raise ValueError("sentence token counts must be positive")
    if any(not math.isfinite(sentence.relevance) for sentence in sentences):
        raise ValueError("sentence relevance scores must be finite")

    eligible = [
        (index, sentence)
        for index, sentence in enumerate(sentences)
        if sentence.relevance >= relevance_threshold and sentence.token_count <= token_budget
    ]
    ranked = sorted(
        eligible,
        key=lambda row: (
            -(row[1].relevance / row[1].token_count),
            -row[1].relevance,
            row[0],
        ),
    )
    selected: set[int] = set()
    used = 0
    for index, sentence in ranked:
        if used + sentence.token_count <= token_budget:
            selected.add(index)
            used += sentence.token_count
    selected_ids = tuple(sentences[index].sentence_id for index in sorted(selected))
    excluded_ids = tuple(
        sentence.sentence_id
        for index, sentence in enumerate(sentences)
        if index not in selected
    )
    return CompressionResult(
        text=" ".join(sentences[index].text for index in sorted(selected)),
        selected_ids=selected_ids,
        excluded_ids=excluded_ids,
        token_count=used,
    )
