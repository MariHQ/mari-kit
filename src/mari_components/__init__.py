"""Reliable product-knowledge primitives for application-owned agents."""

from .errors import (
    AuthenticationFailure,
    ComponentError,
    IncompleteSnapshot,
    MalformedModelOutput,
    PermanentFailure,
    TransientFailure,
)
from .types import (
    AnswerCandidate,
    ChangeHint,
    DecisionCandidate,
    DocumentACL,
    Evidence,
    FactCandidate,
    GlossaryCandidate,
    KnowledgeDocument,
    PollPage,
    PollRequest,
    Principal,
    SyncMode,
    Tombstone,
)

__all__ = [
    "AnswerCandidate",
    "AuthenticationFailure",
    "ChangeHint",
    "ComponentError",
    "DecisionCandidate",
    "DocumentACL",
    "Evidence",
    "FactCandidate",
    "GlossaryCandidate",
    "IncompleteSnapshot",
    "KnowledgeDocument",
    "MalformedModelOutput",
    "PermanentFailure",
    "PollPage",
    "PollRequest",
    "Principal",
    "SyncMode",
    "Tombstone",
    "TransientFailure",
]
