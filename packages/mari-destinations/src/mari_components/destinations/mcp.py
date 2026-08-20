"""MCP destination values and validation independent of a host product."""

from __future__ import annotations

import re
from dataclasses import dataclass


CAPABILITIES = frozenset({"search", "facts", "glossary", "chat", "lineage", "answers"})


@dataclass(frozen=True, slots=True)
class McpServerSpec:
    name: str
    slug: str
    scope: str
    capabilities: tuple[str, ...]


def server_spec(name: str, scope: str, capabilities) -> McpServerSpec:
    clean_name = (name or "").strip()
    if not clean_name:
        raise ValueError("An MCP server needs a name.")
    clean_scope = (scope or "").strip()
    if not clean_scope:
        raise ValueError("An MCP server needs a scope.")
    values = tuple(dict.fromkeys(
        value for value in capabilities or ()
        if isinstance(value, str) and value in CAPABILITIES
    ))
    if not values:
        raise ValueError("Choose at least one MCP capability.")
    slug = re.sub(r"[^a-z0-9]+", "-", clean_name.lower()).strip("-") or "server"
    return McpServerSpec(clean_name, slug, clean_scope, values)
