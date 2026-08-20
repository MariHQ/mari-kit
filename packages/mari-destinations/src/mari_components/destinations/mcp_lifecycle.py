"""MCP destination lifecycle over explicit persistence and secret ports."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from mari_components.destinations.mcp import McpServerSpec, server_spec


@dataclass(frozen=True, slots=True)
class McpPorts:
    name_exists: Callable[[int, str], bool]
    insert: Callable[[int, McpServerSpec, str, str, int], None]
    update: Callable[[int, int, str | None, tuple[str, ...] | None], bool]
    delete: Callable[[int, int], str | None]
    inspect: Callable[[int, int], Mapping[str, object] | None]
    capability_counts: Callable[[int, Sequence[str]], Mapping[str, int]]
    mark_connected: Callable[[int, int], None]
    audit: Callable[[str, str, Sequence[tuple[str, str]]], None]
    issue_token: Callable[[], str]


def create_server(
    project_id: int, name: str, scope: str, capabilities,
    *, base_url: str, ports: McpPorts,
) -> str:
    spec = server_spec(name, scope, capabilities)
    if ports.name_exists(project_id, spec.name):
        raise ValueError(f"An MCP server called '{spec.name}' already exists.")
    token = ports.issue_token()
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    url = f"{base_url.rstrip('/')}/mcp/{spec.slug}"
    ports.insert(project_id, spec, url, token_hash, len(spec.capabilities))
    ports.audit("created MCP server", spec.name, (
        ("Scope", spec.scope), ("Capabilities", ", ".join(spec.capabilities)),
    ))
    return token


def update_server(
    project_id: int, server_id: int, *, scope: str | None,
    capabilities, ports: McpPorts,
) -> bool:
    clean_scope = scope.strip() if isinstance(scope, str) and scope.strip() else None
    clean_caps = None
    if capabilities is not None:
        clean_caps = server_spec("temporary", clean_scope or "existing", capabilities).capabilities
    changed = ports.update(project_id, server_id, clean_scope, clean_caps)
    if changed:
        ports.audit("updated MCP server", str(server_id), ())
    return changed


def delete_server(project_id: int, server_id: int, *, ports: McpPorts) -> bool:
    name = ports.delete(project_id, server_id)
    if name is None:
        return False
    ports.audit("deleted MCP server", name, ())
    return True


def test_server(project_id: int, server_id: int, *, ports: McpPorts) -> dict:
    started = time.perf_counter()
    server = ports.inspect(project_id, server_id)
    if server is None:
        return {"ok": False, "error": "not found"}
    capabilities = tuple(server.get("capabilities") or ("search",))
    counts = ports.capability_counts(project_id, capabilities)
    ports.mark_connected(project_id, server_id)
    return {
        "ok": True,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "checks": dict(counts),
    }
