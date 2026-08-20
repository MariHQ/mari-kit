"""Storage-neutral document visibility decisions."""

from __future__ import annotations

from collections.abc import Collection


SHARED_VISIBILITIES = frozenset({"public", "project", "connector_scope"})


def document_visible(
    visibility: str,
    document_principals: Collection[str],
    caller_principals: Collection[str],
    *,
    project_member: bool,
) -> bool:
    if project_member or visibility in SHARED_VISIBILITIES:
        return True
    return bool(set(document_principals).intersection(caller_principals))
