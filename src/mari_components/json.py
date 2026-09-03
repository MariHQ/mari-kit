"""Provider-neutral JSON generation contracts and validation."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any

from .errors import MalformedModelOutput

JsonGenerator = Callable[[str, str], Any]


def to_json_value(value: Any) -> Any:
    """Recursively encode Mari values without copying MappingProxyType objects."""

    if isinstance(value, Enum):
        return to_json_value(value.value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dt.datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("JSON datetimes must be timezone-aware")
        return value.astimezone(dt.UTC).isoformat().replace("+00:00", "Z")
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: to_json_value(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("JSON mapping keys must be strings")
            result[key] = to_json_value(item)
        return result
    if isinstance(value, (tuple, list)):
        return [to_json_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [to_json_value(item) for item in sorted(value, key=repr)]
    raise TypeError(f"unsupported JSON value: {type(value).__qualname__}")


def require_object(value: Any, *, recipe: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise MalformedModelOutput(f"{recipe} must return a JSON object")
    return value


def require_list(value: Any, key: str, *, recipe: str) -> list[Mapping[str, Any]]:
    rows = require_object(value, recipe=recipe).get(key)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise MalformedModelOutput(f"{recipe}.{key} must be a JSON array of objects")
    return rows
