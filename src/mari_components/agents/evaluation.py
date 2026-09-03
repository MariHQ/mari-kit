"""Small, framework-neutral checks over normalized agent events."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .events import AgentEvent, EventKind


@dataclass(frozen=True, slots=True, kw_only=True)
class EvalResult:
    passed: bool
    checks: Mapping[str, bool]

    def __post_init__(self) -> None:
        object.__setattr__(self, "checks", MappingProxyType(dict(self.checks)))


def evaluate_tools(
    events: Iterable[AgentEvent],
    *,
    expected_tools: Iterable[str],
    require_success: bool = True,
) -> EvalResult:
    values = tuple(events)
    called = tuple(event.name for event in values if event.kind is EventKind.TOOL_CALL)
    results = tuple(event for event in values if event.kind is EventKind.TOOL_RESULT)
    failures = tuple(event for event in results if event.ok is False)
    unknown = tuple(event for event in results if event.ok is None)
    checks = {
        "tools": called == tuple(expected_tools),
        "success": not require_success or (not failures and not unknown),
    }
    return EvalResult(passed=all(checks.values()), checks=checks)


def evaluate_outcome(
    *,
    paths: Iterable[str] = (),
    expected_paths: Iterable[str] = (),
    tool_results: Iterable[tuple[str, bool]] = (),
    expected_tools: Iterable[str] = (),
    completed: bool = True,
    require_completion: bool = True,
    require_tool_success: bool = True,
) -> EvalResult:
    observed_paths = tuple(paths)
    results = tuple(tool_results)
    expected_tool_values = tuple(expected_tools)
    successful_tools = tuple(name for name, ok in results if ok)
    checks = {
        "completed": completed or not require_completion,
        "paths": all(path in observed_paths for path in expected_paths),
        "tools": not expected_tool_values or successful_tools == expected_tool_values,
        "tool_success": not require_tool_success or all(ok for _name, ok in results),
    }
    return EvalResult(passed=all(checks.values()), checks=checks)
