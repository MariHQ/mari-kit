"""Interactive knowledge-chat destination lifecycle over explicit ports."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KnowledgeChatPorts:
    create: Callable[[int, str, str, str, str], int]
    update: Callable[[int, int, str, str, str], bool]
    deploy: Callable[[int, int], tuple[str, str] | None]
    audit: Callable[[str, str], None]


def create(project_id: int, name: str, slug: str, title: str, welcome: str,
           *, ports: KnowledgeChatPorts) -> int:
    name, slug = (name or "").strip(), (slug or "").strip().lower()
    title, welcome = (title or "").strip(), (welcome or "").strip()
    if not name or not title:
        raise ValueError("A knowledge chat needs a name and assistant title.")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("URL slug must contain lowercase letters, numbers, and single hyphens.")
    destination_id = ports.create(project_id, name, slug, title, welcome)
    ports.audit("created knowledge chat", name)
    return destination_id


def update(project_id: int, destination_id: int, name: str, title: str, welcome: str,
           *, ports: KnowledgeChatPorts) -> bool:
    name, title, welcome = (name or "").strip(), (title or "").strip(), (welcome or "").strip()
    if not name or not title:
        raise ValueError("A knowledge chat needs a name and assistant title.")
    changed = ports.update(project_id, destination_id, name, title, welcome)
    if changed:
        ports.audit("updated knowledge chat", name)
    return changed


def deploy(project_id: int, destination_id: int, *, ports: KnowledgeChatPorts) -> str:
    deployed = ports.deploy(project_id, destination_id)
    if deployed is None:
        raise ValueError("Knowledge chat not found in this project.")
    name, path = deployed
    ports.audit("deployed knowledge chat", name)
    return path
