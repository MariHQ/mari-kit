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
    KnowledgeSection,
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
    "KnowledgeSection",
    "MalformedModelOutput",
    "PermanentFailure",
    "PollPage",
    "PollRequest",
    "Principal",
    "SyncMode",
    "Tombstone",
    "TransientFailure",
]
