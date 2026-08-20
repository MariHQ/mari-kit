"""Streaming tool loop; hosts own transport, sessions, authorization, and telemetry."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Mapping

from mari_components.errors import MalformedModelOutput, PermanentFailure
from mari_components.json import JsonGenerator, require_object


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    description: str
    call: Callable[[Mapping[str, Any]], Any]
    writes: bool = False


@dataclass(frozen=True, slots=True)
class AgentEvent:
    kind: str
    name: str = ""
    arguments: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    result: Any = None
    ok: bool = True


AnswerStream = Callable[[Sequence[Mapping[str, str]]], Iterable[str]]


def run_tool_loop(
    messages: Sequence[Mapping[str, str]],
    tools: Sequence[Tool],
    *,
    generate_json: JsonGenerator,
    stream_answer: AnswerStream,
    authorize_write: Callable[[Tool, Mapping[str, Any]], bool],
    observe: Callable[[AgentEvent], None] | None = None,
    maximum_steps: int = 8,
) -> Iterator[AgentEvent]:
    """Lazily execute a bounded loop and yield every event immediately.

    ``generate_json`` only chooses between a tool call and final answer
    generation. ``stream_answer`` owns provider-specific text streaming. The
    loop never assembles answer chunks or stores emitted events. Observer
    failures propagate; a host can explicitly wrap a best-effort telemetry
    sink. Stopping iteration applies backpressure and stops further work.
    """
    if maximum_steps < 1:
        raise ValueError("maximum_steps must be positive")
    by_name = {tool.name: tool for tool in tools}
    if len(by_name) != len(tools) or any(not name for name in by_name):
        raise ValueError("tool names must be non-empty and unique")
    transcript = [dict(message) for message in messages]
    catalog = "\n".join(
        f"- {tool.name}: {tool.description}{' [write]' if tool.writes else ''}"
        for tool in tools
    )

    def emit(event: AgentEvent) -> AgentEvent:
        if observe is not None:
            observe(event)
        return event

    for _step in range(1, maximum_steps + 1):
        prompt = (
            "Choose exactly one action. Use tools only when needed and never invent a tool result. "
            'Return JSON {"action":"tool","tool":"name","arguments":{}} or '
            '{"action":"answer"}.\nTools:\n' + catalog + "\nConversation:\n" + repr(transcript)
        )
        decision = require_object(generate_json(prompt, "agent-loop-v2"), recipe="agent-loop-v2")
        action = str(decision.get("action") or "")
        if action == "answer":
            emitted = False
            for chunk in stream_answer(tuple(transcript)):
                if not isinstance(chunk, str):
                    raise MalformedModelOutput("answer stream chunks must be strings")
                if not chunk:
                    continue
                emitted = True
                yield emit(AgentEvent("answer_delta", result=chunk))
            if not emitted:
                raise MalformedModelOutput("answer stream produced no text")
            yield emit(AgentEvent("answer_complete"))
            return
        if action != "tool":
            raise MalformedModelOutput("agent action must be tool or answer")
        name = str(decision.get("tool") or "")
        arguments = decision.get("arguments")
        if name not in by_name or not isinstance(arguments, dict):
            raise MalformedModelOutput("agent selected an unknown tool or invalid arguments")
        tool = by_name[name]
        safe_arguments = MappingProxyType(dict(arguments))
        yield emit(AgentEvent("tool_call", name, safe_arguments))
        if tool.writes and not authorize_write(tool, safe_arguments):
            result = AgentEvent(
                "tool_result", name, safe_arguments, "write not authorized", False,
            )
            yield emit(result)
            transcript.append({"role": "tool", "content": f"{name}: write not authorized"})
            continue
        try:
            value = tool.call(safe_arguments)
        except Exception as error:
            result = AgentEvent(
                "tool_result", name, safe_arguments, type(error).__name__, False,
            )
            yield emit(result)
            transcript.append({"role": "tool", "content": f"{name}: failed ({type(error).__name__})"})
            continue
        yield emit(AgentEvent("tool_result", name, safe_arguments, value, True))
        transcript.append({"role": "tool", "content": f"{name}: {value!r}"[:4000]})
    raise PermanentFailure("agent reached the explicit tool-step limit")
