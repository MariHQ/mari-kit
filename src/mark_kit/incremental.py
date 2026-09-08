"""Indexed, process-local dependency planning. Persistence remains host-owned."""

from __future__ import annotations

import heapq
from collections import defaultdict
from collections.abc import Iterable

from .dependencies import (
    DependencyKey,
    DependencyStamp,
    DependencyUpdate,
    DependencyUpdatePlan,
    DerivationSpec,
    MaterializationReceipt,
    UpdateAction,
    plan_dependency_updates,
)


class DependencyIndex:
    """Cache snapshot-planner decisions and reevaluate an affected frontier.

    Source/receipt deltas visit direct dependents, propagating only a change in
    availability, blocked state, or completed fingerprint. Topology edits rebuild
    the index with cycle validation. This object is single-writer and performs no
    I/O. It trusts completed receipts exactly as the snapshot planner does.
    """

    def __init__(
        self,
        *,
        sources: Iterable[DependencyStamp] = (),
        derivations: Iterable[DerivationSpec] = (),
        materializations: Iterable[MaterializationReceipt] = (),
    ) -> None:
        sources, derivations, materializations = (
            tuple(sources),
            tuple(derivations),
            tuple(materializations),
        )
        plan = plan_dependency_updates(
            sources=sources, derivations=derivations, materializations=materializations
        )
        self._sources = {s.dependency: s for s in sources}
        self._specs = {s.output: s for s in derivations}
        self._receipts = {r.output.dependency: r for r in materializations}
        self._updates = {u.output: u for u in plan.updates}
        self._available = {s.dependency: s for s in plan.available}
        self._order = tuple(u.output for u in plan.updates)
        self._rank = {key: i for i, key in enumerate(self._order)}
        self._reverse: dict[DependencyKey, set[DependencyKey]] = defaultdict(set)
        for spec in derivations:
            for key in spec.inputs:
                self._reverse[key].add(spec.output)
        self.last_evaluated = self._order

    def apply(
        self,
        *,
        sources: Iterable[DependencyStamp] = (),
        removed_sources: Iterable[DependencyKey] = (),
        materializations: Iterable[MaterializationReceipt] = (),
        evicted_outputs: Iterable[DependencyKey] = (),
        derivations: Iterable[DerivationSpec] = (),
        removed_derivations: Iterable[DependencyKey] = (),
    ) -> tuple[DependencyKey, ...]:
        """Apply explicit deltas; return evaluated outputs in topological order.

        An omitted source is unchanged in THIS delta API. Use removed_sources for
        deletion. Invalid duplicate/conflicting edits or cycles leave state intact.
        Evict an output's receipt whenever its stored material is unavailable.
        """
        sources, materializations, derivations = (
            tuple(sources),
            tuple(materializations),
            tuple(derivations),
        )
        removed_sources, evicted_outputs, removed_derivations = (
            set(removed_sources),
            set(evicted_outputs),
            set(removed_derivations),
        )
        for keys, removed in (
            ([s.dependency for s in sources], removed_sources),
            ([r.output.dependency for r in materializations], evicted_outputs),
            ([s.output for s in derivations], removed_derivations),
        ):
            if len(set(keys)) != len(keys) or set(keys) & removed:
                raise ValueError("duplicate or conflicting delta edits")
        if derivations or removed_derivations:
            new_sources = dict(self._sources)
            new_specs = dict(self._specs)
            new_receipts = dict(self._receipts)
            for mapping, removed in (
                (new_sources, removed_sources),
                (new_specs, removed_derivations),
                (new_receipts, evicted_outputs),
            ):
                for key in removed:
                    mapping.pop(key, None)
            new_sources.update((s.dependency, s) for s in sources)
            new_specs.update((s.output, s) for s in derivations)
            new_receipts.update((r.output.dependency, r) for r in materializations)
            replacement = DependencyIndex(
                sources=new_sources.values(),
                derivations=new_specs.values(),
                materializations=new_receipts.values(),
            )
            self.__dict__.update(replacement.__dict__)
            return self.last_evaluated
        if any(s.dependency in self._specs for s in sources):
            raise ValueError("dependency outputs must have one producer")
        dirty: set[DependencyKey] = set()
        for key in removed_sources:
            if self._sources.pop(key, None) is not None:
                self._available.pop(key, None)
                dirty.update(self._reverse.get(key, ()))
        for stamp in sources:
            if self._sources.get(stamp.dependency) != stamp:
                self._sources[stamp.dependency] = stamp
                self._available[stamp.dependency] = stamp
                dirty.update(self._reverse.get(stamp.dependency, ()))
        for key in evicted_outputs:
            if self._receipts.pop(key, None) is not None and key in self._specs:
                dirty.add(key)
        for receipt in materializations:
            key = receipt.output.dependency
            if self._receipts.get(key) != receipt:
                self._receipts[key] = receipt
                if key in self._specs:
                    dirty.add(key)
        queue = [self._rank[key] for key in dirty]
        heapq.heapify(queue)
        evaluated = []
        while queue:
            key = self._order[heapq.heappop(queue)]
            dirty.remove(key)
            before = (
                self._available.get(key),
                self._updates[key].action is UpdateAction.BLOCKED,
            )
            update = self._evaluate(key)
            self._updates[key] = update
            if update.action is UpdateAction.REUSE:
                self._available[key] = self._receipts[key].output
            else:
                self._available.pop(key, None)
            evaluated.append(key)
            after = (self._available.get(key), update.action is UpdateAction.BLOCKED)
            if before != after:
                for dependent in self._reverse.get(key, ()):
                    if dependent not in dirty:
                        dirty.add(dependent)
                        heapq.heappush(queue, self._rank[dependent])
        self.last_evaluated = tuple(evaluated)
        return self.last_evaluated

    def _evaluate(self, key: DependencyKey) -> DependencyUpdate:
        spec = self._specs[key]
        missing = tuple(
            dep
            for dep in spec.inputs
            if (dep not in self._specs and dep not in self._available)
            or (
                dep in self._updates
                and self._updates[dep].action is UpdateAction.BLOCKED
            )
        )
        waiting = tuple(
            dep
            for dep in spec.inputs
            if dep in self._specs and dep not in self._available
        )
        if missing or waiting:
            return DependencyUpdate(
                output=key,
                action=UpdateAction.BLOCKED if missing else UpdateAction.WAIT,
                reasons=("unavailable_input" if missing else "upstream_pending",),
                dependencies=missing or waiting,
            )
        receipt = self._receipts.get(key)
        return plan_dependency_updates(
            sources=(self._available[dep] for dep in spec.inputs),
            derivations=(spec,),
            materializations=(receipt,) if receipt else (),
        ).updates[0]

    def plan(
        self, *, targets: Iterable[DependencyKey] | None = None
    ) -> DependencyUpdatePlan:
        """Read cached decisions, optionally restricted to targets and ancestors.

        Selection limits the returned work, not index maintenance. Full plan
        serialization costs O(graph size), even after a small incremental update.
        Retirement hints are global to this index, not inferred from target omission.
        """
        if targets is None:
            keys = self._order
            available = self._available
        else:
            needed: set[DependencyKey] = set()
            pending = list(targets)
            for target in pending:
                if target not in self._specs and target not in self._sources:
                    raise ValueError("unknown dependency target")
            while pending:
                key = pending.pop()
                if key in needed:
                    continue
                needed.add(key)
                if key in self._specs:
                    pending.extend(self._specs[key].inputs)
            keys = tuple(
                sorted(needed & self._specs.keys(), key=self._rank.__getitem__)
            )
            available = {
                key: self._available[key] for key in needed if key in self._available
            }
        return DependencyUpdatePlan(
            updates=tuple(self._updates[key] for key in keys),
            available=tuple(
                available[key] for key in sorted(available, key=lambda key: key.key)
            ),
            retired=tuple(
                sorted(
                    self._receipts.keys() - self._specs.keys(), key=lambda key: key.key
                )
            ),
        )
