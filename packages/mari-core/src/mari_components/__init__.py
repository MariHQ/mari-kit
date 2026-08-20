"""Composable functions for building product-knowledge systems.

The package deliberately owns no process lifecycle, persistence, identity,
model client, or configuration discovery. Public operations receive their
dependencies explicitly.
"""

from .errors import (
    AuthenticationFailure,
    ComponentError,
    IncompleteSnapshot,
    MalformedModelOutput,
    PermanentFailure,
    RateLimitFailure,
    TransientFailure,
)
from .types import (
    ChangeHint,
    DocumentACL,
    Evidence,
    KnowledgeDocument,
    PollPage,
    PollRequest,
    Principal,
    SyncMode,
    Tombstone,
    Upsert,
)
from .documents import DocumentVersion, document_key

__all__ = [
    "AuthenticationFailure",
    "ChangeHint",
    "ComponentError",
    "DocumentACL",
    "DocumentVersion",
    "Evidence",
    "IncompleteSnapshot",
    "KnowledgeDocument",
    "MalformedModelOutput",
    "PermanentFailure",
    "PollPage",
    "PollRequest",
    "Principal",
    "RateLimitFailure",
    "SyncMode",
    "Tombstone",
    "TransientFailure",
    "Upsert",
    "document_key",
]
