"""Small event values for evaluating runs produced by an agent framework.

Mari Components does not execute agents. Hosts translate the native events from
OpenAI Agents SDK, LangChain/LangGraph, PydanticAI, or another runtime into
these values only when they want to use the framework-neutral evaluators.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from mari_components.json import freeze_json_mapping


class EventKind(StrEnum):
    TOOL_PROPOSAL = "tool_proposal"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ANSWER = "answer"
    ERROR = "error"


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentEvent:
    kind: EventKind
    name: str = ""
    arguments: Mapping[str, Any] = field(
        default_factory=dict,
    )
    result: Any = None
    ok: bool | None = True
    speculative: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.kind, EventKind):
            raise TypeError("agent event kind must be an EventKind")
        if (
            self.kind
            in {EventKind.TOOL_PROPOSAL, EventKind.TOOL_CALL, EventKind.TOOL_RESULT}
            and not self.name.strip()
        ):
            raise ValueError("tool events require a name")
        object.__setattr__(self, "arguments", freeze_json_mapping(self.arguments))
