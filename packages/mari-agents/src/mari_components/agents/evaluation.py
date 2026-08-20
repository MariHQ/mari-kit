"""Outcome-based evaluation independent of any product UI routes."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Iterable

from .loop import AgentEvent


@dataclass(frozen=True, slots=True)
class EvalCase:
    name: str
    required_terms: tuple[str, ...] = ()
    forbidden_terms: tuple[str, ...] = ()
    require_citations: bool = False


@dataclass(frozen=True, slots=True)
class ToolEvalCase:
    name: str
    expected_tools: tuple[str, ...]
    require_success: bool = True


@dataclass(frozen=True, slots=True)
class EvalResult:
    case: str
    passed: bool
    checks: dict[str, bool]


@dataclass(frozen=True, slots=True)
class OutcomeEvalCase:
    """Provider/UI-neutral expectations for a completed agent interaction."""
    name: str
    required_terms: tuple[str, ...] = ()
    expected_paths: tuple[str, ...] = ()
    expected_tools: tuple[str, ...] = ()
    require_completion: bool = True
    require_tool_success: bool = True


def parse_sse_events(chunks: Iterable[str]) -> list[tuple[str, dict]]:
    """Parse named JSON server-sent events from an iterable of frames."""
    events: list[tuple[str, dict]] = []
    for chunk in chunks:
        event = ""
        data: list[str] = []
        for line in chunk.splitlines():
            if line.startswith("event:"):
                event = line.partition(":")[2].strip()
            elif line.startswith("data:"):
                data.append(line.partition(":")[2].lstrip())
        if event and data:
            events.append((event, json.loads("\n".join(data))))
    return events


def evaluate_answer(case: EvalCase, answer: str, *, citation_count: int = 0) -> EvalResult:
    normalized = answer.casefold()
    checks = {
        "required_terms": all(term.casefold() in normalized for term in case.required_terms),
        "forbidden_terms": all(term.casefold() not in normalized for term in case.forbidden_terms),
        "citations": not case.require_citations or citation_count > 0,
        "non_empty": bool(answer.strip()),
    }
    return EvalResult(case.name, all(checks.values()), checks)


def evaluate_tools(case: ToolEvalCase, events: Iterable[AgentEvent]) -> EvalResult:
    values = tuple(events)
    called = tuple(event.name for event in values if event.kind == "tool_call")
    failures = tuple(event for event in values if event.kind == "tool_result" and not event.ok)
    checks = {"tools": called == case.expected_tools, "success": not case.require_success or not failures}
    return EvalResult(case.name, all(checks.values()), checks)


def evaluate_outcome(
    case: OutcomeEvalCase,
    answer: str,
    *,
    paths: Iterable[str] = (),
    tool_results: Iterable[tuple[str, bool]] = (),
    completed: bool = True,
) -> EvalResult:
    normalized = answer.casefold()
    observed_paths = tuple(paths)
    results = tuple(tool_results)
    successful_tools = tuple(name for name, ok in results if ok)
    checks = {
        "completed": completed or not case.require_completion,
        "required_terms": all(term.casefold() in normalized for term in case.required_terms),
        "paths": all(path in observed_paths for path in case.expected_paths),
        "tools": not case.expected_tools or successful_tools == case.expected_tools,
        "tool_success": not case.require_tool_success or all(ok for _name, ok in results),
    }
    return EvalResult(case.name, all(checks.values()), checks)
