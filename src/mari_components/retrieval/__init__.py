"""Candidate generation, rank fusion, graph propagation, and exact reranking."""

from .fusion import (
    DiversifiedHit,
    FusedHit,
    RankContribution,
    maximal_marginal_relevance,
    reciprocal_rank_fusion,
)
from .graph import GraphHit, PageRankResult, personalized_pagerank, project_graph_scores
from .index import MuveraIndex, RetrievalHit, build_index, search_index
from .maxsim import exact_maxsim
from .muvera import FDEConfig
from .research import (
    ActiveRetrievalQuery,
    CompressionResult,
    CompressionSentence,
    CorrectiveAction,
    CorrectiveRetrievalPlan,
    SummaryTree,
    SummaryTreeNode,
    TreeWalk,
    build_summary_tree,
    hypothetical_document_embedding,
    plan_active_retrieval,
    plan_corrective_retrieval,
    selective_compression,
    walk_summary_tree,
)
from .serialization import deserialize_index, serialize_index

__all__ = [
    "ActiveRetrievalQuery",
    "CompressionResult",
    "CompressionSentence",
    "CorrectiveAction",
    "CorrectiveRetrievalPlan",
    "DiversifiedHit",
    "FDEConfig",
    "FusedHit",
    "GraphHit",
    "MuveraIndex",
    "PageRankResult",
    "RankContribution",
    "RetrievalHit",
    "SummaryTree",
    "SummaryTreeNode",
    "TreeWalk",
    "build_index",
    "build_summary_tree",
    "deserialize_index",
    "exact_maxsim",
    "hypothetical_document_embedding",
    "maximal_marginal_relevance",
    "personalized_pagerank",
    "plan_active_retrieval",
    "plan_corrective_retrieval",
    "project_graph_scores",
    "reciprocal_rank_fusion",
    "search_index",
    "selective_compression",
    "serialize_index",
    "walk_summary_tree",
]
