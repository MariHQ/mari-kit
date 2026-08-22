"""Framework-neutral event normalization and outcome evaluation helpers.

Agent execution belongs to an established runtime such as OpenAI Agents SDK,
LangChain/LangGraph, or PydanticAI. This module deliberately provides no loop.
"""

from .evaluation import EvalResult, evaluate_outcome, evaluate_tools
from .events import AgentEvent, EventKind

__all__ = [
    "AgentEvent",
    "EvalResult",
    "EventKind",
    "evaluate_outcome",
    "evaluate_tools",
]
