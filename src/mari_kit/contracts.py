"""Backend-neutral boundaries used to compose Mari algorithms."""

from __future__ import annotations

import datetime as dt
from collections.abc import Collection, Sequence
from typing import Protocol, TypeVar, runtime_checkable

from .references import ObjectRef, RevisionRef

PrincipalT = TypeVar("PrincipalT", contravariant=True)
QueryT = TypeVar("QueryT", contravariant=True)
HitT = TypeVar("HitT", covariant=True)
ValueT = TypeVar("ValueT")
ResolvedT = TypeVar("ResolvedT", covariant=True)
RefT = TypeVar("RefT", contravariant=True)


@runtime_checkable
class Clock(Protocol):
    def __call__(self) -> dt.datetime: ...


@runtime_checkable
class Authorizer(Protocol[PrincipalT]):
    def __call__(self, principal: PrincipalT, ref: ObjectRef) -> bool: ...


@runtime_checkable
class Serializer(Protocol[ValueT]):
    def encode(self, value: ValueT) -> bytes: ...

    def decode(self, value: bytes) -> ValueT: ...


@runtime_checkable
class KnowledgeIndex(Protocol[QueryT, HitT, RefT]):
    """A retrieval boundary whose authorization set is explicit at query time."""

    def search(
        self,
        query: QueryT,
        *,
        limit: int,
        allowed_refs: Collection[RefT] | None = None,
    ) -> Sequence[HitT]: ...


@runtime_checkable
class RevisionResolver(Protocol[ResolvedT]):
    def __call__(self, ref: RevisionRef) -> ResolvedT | None: ...
