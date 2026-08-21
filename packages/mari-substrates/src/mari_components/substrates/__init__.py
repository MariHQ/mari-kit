"""Ports for using an external search and ingestion substrate.

The values in this package deliberately contain no Onyx, Glean, HTTP, model,
database, or framework code.  An application selects one adapter and Mari's
knowledge-management layer consumes this contract.
"""

from .protocol import KnowledgeSubstrate
from .types import (
    Capability,
    Document,
    SearchHit,
    SearchRequest,
    Source,
    SourceRegistration,
    SubstrateInfo,
    TextSection,
    UpsertResult,
)

__all__ = [
    "Capability",
    "Document",
    "KnowledgeSubstrate",
    "SearchHit",
    "SearchRequest",
    "Source",
    "SourceRegistration",
    "SubstrateInfo",
    "TextSection",
    "UpsertResult",
]
