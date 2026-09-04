"""Behavioral checks for application-owned boundary implementations."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from mari_components.contracts import Authorizer, Clock, KnowledgeIndex, Serializer
from mari_components.references import ObjectRef


def assert_clock_conforms(clock: Clock) -> None:
    first = clock()
    second = clock()
    assert first.tzinfo is not None and first.utcoffset() is not None
    assert second.tzinfo is not None and second.utcoffset() is not None
    assert second >= first


def assert_serializer_conforms(
    serializer: Serializer[Any], values: Iterable[object]
) -> None:
    for value in values:
        encoded = serializer.encode(value)
        assert isinstance(encoded, bytes)
        assert serializer.decode(encoded) == value
        assert serializer.encode(value) == encoded


def assert_authorizer_conforms(
    authorizer: Authorizer[Any],
    *,
    principal: object,
    allowed_ref: ObjectRef,
    denied_ref: ObjectRef,
) -> None:
    assert authorizer(principal, allowed_ref)
    assert not authorizer(principal, denied_ref)


def assert_index_authorization_conforms(
    index: KnowledgeIndex[Any, Any, Any],
    *,
    query: object,
    allowed_ref: object,
    hit_ref: Callable[[object], object],
) -> None:
    allowed = index.search(query, limit=10, allowed_refs={allowed_ref})
    assert all(hit_ref(hit) == allowed_ref for hit in allowed)
    assert not index.search(query, limit=10, allowed_refs=set())
