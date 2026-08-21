"""Streaming agent use case over injected model, persistence, and telemetry ports."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from mari_components.agents.loop import Tool, ToolAuth, run_tool_loop


@dataclass(frozen=True, slots=True)
class ToolOutcome:
    ok: bool
    summary: str
    detail: Any
    navigation: str = ""
    evidence: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class ToolBinding:
    description: str
    call: Callable[[Mapping[str, Any]], ToolOutcome]
    writes: bool = False
    input_schema: Mapping[str, Any] | None = None
    auth: ToolAuth | None = None


@dataclass(frozen=True, slots=True)
class AgentOutput:
    kind: str
    payload: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class AgentPorts:
    history: Callable[[int], Sequence[Mapping[str, str]]]
    plan: Callable[[str, str], Any]
    answer: Callable[[Sequence[Mapping[str, str]]], Iterable[str]]
    save_answer: Callable[[int, str, Sequence[Mapping[str, Any]]], None]
    observe_trajectory: Callable[[int, str, Sequence[Mapping[str, Any]], str], None]
    record_usage: Callable[[str, str], None]
    authorize_tool: Callable[[Tool, Mapping[str, Any]], bool] | None = None
    authorize_write: Callable[[Tool, Mapping[str, Any]], bool] | None = None


def _tools(bindings: Mapping[str, ToolBinding]) -> tuple[Tool, ...]:
    return tuple(
        Tool(name, binding.description, binding.call, binding.writes,
             binding.input_schema or {}, binding.auth)
        for name, binding in bindings.items()
    )


def stream_agent_turn(
    session_id: int,
    message: str,
    bindings: Mapping[str, ToolBinding],
    ports: AgentPorts,
    *,
    maximum_steps: int = 8,
    minimum_tool_observations: int = 0,
) -> Iterator[AgentOutput]:
    """Execute one agent turn and emit transport-neutral events immediately."""
    messages = [dict(row) for row in ports.history(session_id)]
    user_message = {"role": "user", "content": message[:2000]}
    if not messages or messages[-1] != user_message:
        messages.append(user_message)

    trace: list[Mapping[str, Any]] = []
    answer_parts: list[str] = []
    evidence: list[Mapping[str, Any]] = []
    try:
        events = run_tool_loop(
            messages,
            _tools(bindings),
            generate_json=ports.plan,
            stream_answer=ports.answer,
            authorize_write=ports.authorize_write or (lambda _tool, _arguments: False),
            authorize_tool=ports.authorize_tool,
            maximum_steps=maximum_steps,
            minimum_tool_observations=minimum_tool_observations,
        )
        for event in events:
            arguments = dict(event.arguments)
            if event.kind == "tool_proposal":
                yield AgentOutput("tool_proposal", {
                    "name": event.name, "args": arguments, "speculative": True,
                })
                continue
            if event.kind == "auth_required":
                auth = event.result
                yield AgentOutput("auth_required", {
                    "name": event.name,
                    "provider": getattr(auth, "provider", ""),
                    "kind": getattr(auth, "kind", ""),
                    "scopes": list(getattr(auth, "scopes", ())),
                    "setup_url": getattr(auth, "setup_url", ""),
                })
                trace.append({
                    "kind": "auth_required", "name": event.name, "args": arguments,
                    "summary": f"Authorization required: {getattr(auth, 'provider', '')}",
                    "ok": False, "speculative": event.speculative,
                })
                continue
            if event.kind == "tool_call":
                yield AgentOutput("tool_start", {
                    "name": event.name, "args": arguments,
                    "speculative": event.speculative,
                })
                continue
            if event.kind == "tool_result":
                outcome = event.result
                if not isinstance(outcome, ToolOutcome):
                    outcome = ToolOutcome(event.ok, str(event.result or ""), event.result)
                if outcome.navigation and outcome.ok:
                    yield AgentOutput("navigate", {"path": outcome.navigation})
                yield AgentOutput("tool_result", {
                    "name": event.name, "summary": outcome.summary, "ok": outcome.ok,
                })
                trace.append({
                    "kind": "tool", "name": event.name, "args": arguments,
                    "summary": outcome.summary, "ok": outcome.ok,
                    "speculative": event.speculative,
                    "evidence": [dict(row) for row in outcome.evidence],
                })
                evidence.extend(outcome.evidence)
                continue
            if event.kind == "answer_delta":
                token = str(event.result)
                answer_parts.append(token)
                yield AgentOutput("token", {"token": token})
    except Exception as error:
        yield AgentOutput("warning", {
            "message": f"Agent execution stopped: {type(error).__name__}",
        })

    seen_documents: set[str] = set()
    source_titles: list[str] = []
    for item in evidence:
        identity = str(item.get("document_id") or item.get("title") or "")
        title = str(item.get("title") or "").strip()
        if not identity or not title or identity in seen_documents:
            continue
        seen_documents.add(identity)
        source_titles.append(title)
        if len(source_titles) == 3:
            break
    if source_titles:
        citations = "\n\nSources: " + "; ".join(
            f"[{index}] {title}" for index, title in enumerate(source_titles, 1)
        )
        answer_parts.append(citations)
        yield AgentOutput("token", {"token": citations})

    answer = "".join(answer_parts)
    try:
        ports.save_answer(session_id, answer, trace)
    except Exception:
        yield AgentOutput("warning", {"message": "The answer could not be persisted."})
    try:
        ports.record_usage("chat_answer", "agent-tools-v2")
    except Exception:
        pass
    try:
        ports.observe_trajectory(session_id, message, trace, "agent-tools-v2")
    except Exception:
        pass
    yield AgentOutput("done", {"session_id": session_id})
