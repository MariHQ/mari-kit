"""Temporal graph, entity-resolution, and projection primitives."""

from .communities import (
    CommunityPartition,
    CommunityReport,
    build_community_reports,
    leiden_communities,
    map_reduce_reports,
)
from .resolution import (
    FieldAgreement,
    ResolutionDecision,
    ResolutionResult,
    fellegi_sunter_score,
    resolve_entity,
)
from .temporal import TemporalFact, close_transaction, query_temporal_facts

__all__ = [
    "CommunityPartition",
    "CommunityReport",
    "FieldAgreement",
    "ResolutionDecision",
    "ResolutionResult",
    "TemporalFact",
    "build_community_reports",
    "close_transaction",
    "fellegi_sunter_score",
    "query_temporal_facts",
    "leiden_communities",
    "map_reduce_reports",
    "resolve_entity",
]
