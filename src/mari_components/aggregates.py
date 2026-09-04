"""Reversible, keyed delta aggregates with exact arithmetic for numeric sums."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType
from typing import Any, Generic, Protocol, TypeVar

from .dependencies import DependencyKey, DependencyStamp, dependency_fingerprint
from .json import freeze_json_value
from .references import ScopeRef

StateT = TypeVar("StateT")


class DeltaReducer(Protocol[StateT]):
    """Pure reversible reducer. Implementations must never mutate prior state."""

    def zero(self) -> StateT: ...
    def change(self, state: StateT, value: Any, sign: int) -> StateT: ...
    def finish(self, state: StateT) -> Any: ...


class DeltaAggregate(Generic[StateT]):
    """Single-writer keyed aggregate. Replayed upserts/deletes are idempotent.

    Values are frozen JSON. Replacement subtracts the old contribution before
    adding the new one. Reducer validation failures leave the index unchanged.
    The host owns snapshot persistence, recipe versioning and synchronization.
    """

    def __init__(self, reducer: DeltaReducer[StateT], *, scope: ScopeRef) -> None:
        self._reducer = reducer
        self._scope = scope
        self._state = reducer.zero()
        self._values: dict[DependencyKey, Any] = {}

    def apply(
        self,
        upserts: Iterable[tuple[DependencyKey, Any]] = (),
        *,
        removed: Iterable[DependencyKey] = (),
    ) -> None:
        rows = tuple((key, freeze_json_value(value)) for key, value in upserts)
        deleted = set(removed)
        keys = [key for key, _ in rows]
        if len(set(keys)) != len(keys) or deleted & set(keys):
            raise ValueError("duplicate or conflicting aggregate edits")
        if any(key.object.scope != self._scope for key in (*keys, *deleted)):
            raise ValueError("aggregate keys must share its scope")
        state = self._state
        edits = dict(rows)
        changed = set(edits) | deleted
        for key in sorted(changed, key=lambda k: k.key):
            if key in edits and key in self._values and edits[key] == self._values[key]:
                continue
            if key in self._values:
                state = self._reducer.change(state, self._values[key], -1)
            if key in edits:
                state = self._reducer.change(state, edits[key], 1)
        # Validate serialization/overflow before publishing any state.
        freeze_json_value(self._reducer.finish(state))
        for key in deleted:
            self._values.pop(key, None)
        self._values.update(edits)
        self._state = state

    @property
    def value(self) -> Any:
        return freeze_json_value(self._reducer.finish(self._state))

    @property
    def contributions(self) -> Mapping[DependencyKey, Any]:
        return MappingProxyType(dict(self._values))

    def stamp(self, output: DependencyKey) -> DependencyStamp:
        if output.object.scope != self._scope:
            raise ValueError("aggregate output must share its scope")
        return DependencyStamp(
            dependency=output, fingerprint=dependency_fingerprint(self.value)
        )


class CountReducer:
    def zero(self) -> int:
        return 0

    def change(self, state: int, value: Any, sign: int) -> int:
        return state + sign

    def finish(self, state: int) -> int:
        return state


@dataclass(frozen=True, slots=True)
class VectorTotals:
    sums: tuple[Fraction, ...] = ()
    weight: Fraction = Fraction(0)
    count: int = 0


class WeightedVectorReducer:
    """Values: {vector: finite numbers, weight: positive number (default 1)}.

    Exposes weighted sums and centroid. Rational accumulation avoids edit-order
    drift; it trades speed and memory for deterministic reference behavior.
    """

    def zero(self) -> VectorTotals:
        return VectorTotals()

    def change(self, state: VectorTotals, value: Any, sign: int) -> VectorTotals:
        if not isinstance(value, Mapping) or not isinstance(value.get("vector"), tuple):
            raise ValueError("weighted vector mapping is required")
        row = value["vector"]
        weight = value.get("weight", 1)
        if not row or any(type(x) not in (int, float) for x in (*row, weight)):
            raise ValueError("vector and weight must be numeric")
        mass = Fraction(str(weight))
        if mass <= 0 or (state.count and len(row) != len(state.sums)):
            raise ValueError("positive weight and consistent vector dimension required")
        sums = state.sums or tuple(Fraction(0) for _ in row)
        count = state.count + sign
        if count == 0:
            return VectorTotals()
        return VectorTotals(
            tuple(
                a + sign * mass * Fraction(str(b))
                for a, b in zip(sums, row, strict=True)
            ),
            state.weight + sign * mass,
            count,
        )

    def finish(self, state: VectorTotals) -> Any:
        return {
            "count": state.count,
            "weight": float(state.weight),
            "sum": tuple(float(x) for x in state.sums),
            "centroid": tuple(float(x / state.weight) for x in state.sums)
            if state.count
            else (),
        }


@dataclass(frozen=True, slots=True)
class LexicalTotals:
    documents: int
    length: int
    frequencies: Mapping[str, int]
    document_frequencies: Mapping[str, int]


def _counts(
    prior: Mapping[str, int], values: Mapping[str, int], sign: int
) -> Mapping[str, int]:
    result = dict(prior)
    for key, count in values.items():
        result[key] = result.get(key, 0) + sign * count
        if result[key] == 0:
            del result[key]
    return MappingProxyType(result)


class LexicalStatisticsReducer:
    """Per-document values are term -> positive integer term frequency maps."""

    def zero(self) -> LexicalTotals:
        return LexicalTotals(0, 0, MappingProxyType({}), MappingProxyType({}))

    def change(self, state: LexicalTotals, value: Any, sign: int) -> LexicalTotals:
        if not isinstance(value, Mapping) or any(
            type(v) is not int or v <= 0 for v in value.values()
        ):
            raise ValueError("term frequencies must be positive integers")
        return LexicalTotals(
            state.documents + sign,
            state.length + sign * sum(value.values()),
            _counts(state.frequencies, value, sign),
            _counts(state.document_frequencies, dict.fromkeys(value, 1), sign),
        )

    def finish(self, state: LexicalTotals) -> Any:
        return {
            "documents": state.documents,
            "total_length": state.length,
            "term_frequencies": state.frequencies,
            "document_frequencies": state.document_frequencies,
        }


class MembershipReducer:
    """Per-source values are unique target strings; retain target reference counts.

    Encode scoped target identities in strings at the host boundary. The aggregate
    contribution map retains each source's exact targets for projection updates.
    """

    def zero(self) -> Mapping[str, int]:
        return MappingProxyType({})

    def change(
        self, state: Mapping[str, int], value: Any, sign: int
    ) -> Mapping[str, int]:
        if not isinstance(value, tuple) or any(
            not isinstance(v, str) or not v for v in value
        ):
            raise ValueError("membership must be a sequence of target strings")
        if len(set(value)) != len(value):
            raise ValueError("duplicate membership targets")
        return _counts(state, dict.fromkeys(value, 1), sign)

    def finish(self, state: Mapping[str, int]) -> Any:
        return state
