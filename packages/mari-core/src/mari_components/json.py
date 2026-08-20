"""Provider-neutral JSON generation contracts and validation."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from .errors import MalformedModelOutput


JsonGenerator = Callable[[str, str], Any]


def require_object(value: Any, *, recipe: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise MalformedModelOutput(f"{recipe} must return a JSON object")
    return value


def require_list(value: Any, key: str, *, recipe: str) -> list[Mapping[str, Any]]:
    rows = require_object(value, recipe=recipe).get(key)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise MalformedModelOutput(f"{recipe}.{key} must be a JSON array of objects")
    return rows
