"""Small execution functions for hosts that persist and schedule workflows themselves."""

from __future__ import annotations

import fnmatch
import time
from collections.abc import Callable, Collection, Mapping, Sequence
from typing import Any


StepResult = tuple[str, str, dict[str, Any]]
StepImplementation = Callable[[dict[str, Any], dict[str, Any]], StepResult]


def run_step(
    kind: str,
    implementation: StepImplementation | None,
    configuration: dict[str, Any],
    context: dict[str, Any],
    *,
    retryable: Collection[str] = (),
    retries: int = 1,
    backoff: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
) -> StepResult:
    if implementation is None:
        return "failed", f"unknown step: {kind}", {}
    attempts = 1 + (max(0, retries) if kind in retryable else 0)
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            status, detail, updates = implementation(configuration, context)
            if attempt:
                detail = f"{detail} (succeeded on retry after: {type(last).__name__}: {last})"[:200]
            return status, detail, updates
        except Exception as error:
            last = error
            if attempt + 1 < attempts:
                sleep(backoff)
    return "failed", f"{type(last).__name__}: {last}"[:140] + (
        f" (after {attempts} attempts)" if attempts > 1 else ""
    ), {}


def matching_documents(
    trigger: Mapping[str, Any],
    change: str,
    documents: Sequence[Mapping[str, Any]],
    document_tags: Mapping[int, set[str]],
) -> list[Mapping[str, Any]]:
    if (trigger.get("on") or "") != change:
        return []
    matched = []
    for document in documents:
        if trigger.get("source_id") is not None and document.get("source_id") != int(trigger["source_id"]):
            continue
        if trigger.get("tag") and trigger["tag"] not in document_tags.get(int(document["id"]), set()):
            continue
        if trigger.get("path_glob") and not fnmatch.fnmatch(
            str(document.get("source_path") or ""), str(trigger["path_glob"]),
        ):
            continue
        matched.append(document)
    return matched
