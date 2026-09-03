"""Parser-neutral results, issues, and stable source identities."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Hashable, Iterable, Mapping, Set
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Generic, TypeVar

ValueT = TypeVar("ValueT")


def _framed(parts: Iterable[bytes]) -> bytes:
    output = bytearray()
    for part in parts:
        output.extend(len(part).to_bytes(8, "big"))
        output.extend(part)
    return bytes(output)


def _stable_component(value: object) -> bytes:
    if value is None:
        return b"none"
    if isinstance(value, bool):
        return b"bool:" + str(value).encode()
    if isinstance(value, int):
        return b"int:" + str(value).encode()
    if isinstance(value, float):
        rendered = "nan" if math.isnan(value) else value.hex()
        return b"float:" + rendered.encode()
    if isinstance(value, str):
        return b"str:" + value.encode()
    if isinstance(value, bytes):
        return b"bytes:" + value
    if isinstance(value, Mapping):
        items = sorted(
            (
                (_stable_component(key), _stable_component(item))
                for key, item in value.items()
            ),
            key=lambda pair: pair[0],
        )
        return b"mapping:" + _framed(
            _framed((key, item)) for key, item in items
        )
    if isinstance(value, tuple):
        return b"tuple:" + _framed(_stable_component(item) for item in value)
    if isinstance(value, list):
        return b"list:" + _framed(_stable_component(item) for item in value)
    if isinstance(value, Set):
        return b"set:" + _framed(
            sorted(_stable_component(item) for item in value)
        )
    return (
        f"{type(value).__module__}.{type(value).__qualname__}:{value!r}"
    ).encode()


class ParseIssueSeverity(StrEnum):
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True, kw_only=True)
class ParseIssue:
    code: str
    message: str
    severity: ParseIssueSeverity = ParseIssueSeverity.ERROR
    subject: Hashable | None = None
    start: int | None = None
    end: int | None = None

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.message.strip():
            raise ValueError("parse issue code and message are required")
        if (self.start is None) != (self.end is None):
            raise ValueError("parse issue start and end must be supplied together")
        if self.start is not None and (
            self.start < 0 or self.end is None or self.end < self.start
        ):
            raise ValueError("parse issue span is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class ParseResult(Generic[ValueT]):
    values: tuple[ValueT, ...]
    issues: tuple[ParseIssue, ...]
    parser: str
    source_revision: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.parser.strip():
            raise ValueError("parser identity is required")
        object.__setattr__(self, "values", tuple(self.values))
        object.__setattr__(self, "issues", tuple(self.issues))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def succeeded(self) -> bool:
        return not any(
            issue.severity is ParseIssueSeverity.ERROR for issue in self.issues
        )


def stable_source_id(
    components: Iterable[object], *, prefix: str = "", digest_bytes: int = 16
) -> str:
    """Hash caller-selected identity components with unambiguous framing."""

    if digest_bytes < 8 or digest_bytes > 32:
        raise ValueError("digest_bytes must be between 8 and 32")
    digest = hashlib.sha256()
    count = 0
    for component in components:
        encoded = _stable_component(component)
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        count += 1
    if not count:
        raise ValueError("at least one identity component is required")
    value = digest.hexdigest()[: digest_bytes * 2]
    return f"{prefix}:{value}" if prefix else value
