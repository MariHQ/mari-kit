"""Workflow lifecycle functions over explicit persistence/execution ports."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .workflow_runtime import matching_documents, run_step


@dataclass(frozen=True, slots=True)
class WorkflowPorts:
    create_run: Callable[[int, int, bool], tuple[int, int, str] | None]
    approve_waiting_run: Callable[[int, int, str], tuple[int, int] | None]
    save: Callable[[int, str, str, Sequence[Mapping[str, Any]], int | None, str, bool], int]
    delete: Callable[[int, int], str | None]
    set_status: Callable[[int, int, str], str | None]
    set_pinned: Callable[[int, int, bool], bool]
    start_run: Callable[[int, int], None]
    audit: Callable[[str, str], None]


def run(project_id: int, workflow_id: int, *, dry_run: bool, ports: WorkflowPorts) -> int:
    created = ports.create_run(project_id, workflow_id, dry_run)
    if created is None:
        raise ValueError("Workflow not found in this project.")
    run_id, number, name = created
    ports.audit(f"started run #{number}", name)
    ports.start_run(run_id, 0)
    return number


def approve(project_id: int, run_id: int, *, actor_name: str, ports: WorkflowPorts) -> bool:
    approved = ports.approve_waiting_run(project_id, run_id, actor_name)
    if approved is None:
        return False
    number, next_step = approved
    ports.audit("approved run", f"#{number}")
    ports.start_run(run_id, next_step)
    return True


def save(project_id: int, name: str, description: str, steps, *, workflow_id: int | None,
         color: str, pinned: bool, ports: WorkflowPorts) -> int:
    clean_name = (name or "").strip()
    if not clean_name:
        raise ValueError("A flow needs a name.")
    saved = ports.save(project_id, clean_name, description, steps, workflow_id, color, pinned)
    ports.audit("updated flow" if workflow_id else "created flow", clean_name)
    return saved


def delete(project_id: int, workflow_id: int, *, ports: WorkflowPorts) -> bool:
    name = ports.delete(project_id, workflow_id)
    if name is None:
        return False
    ports.audit("deleted flow", name)
    return True


def set_status(project_id: int, workflow_id: int, status: str, *, ports: WorkflowPorts) -> bool:
    if status not in {"active", "paused"}:
        raise ValueError("Workflow status must be active or paused.")
    name = ports.set_status(project_id, workflow_id, status)
    if name is None:
        return False
    ports.audit("enabled flow" if status == "active" else "paused flow", name)
    return True
