"""Deterministic overlap lineage across episode/topic/community regrouping."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from .dependencies import dependency_fingerprint
from .references import ObjectRef, ScopeRef


@dataclass(frozen=True, slots=True, kw_only=True)
class GroupIdentity:
    object: ObjectRef
    members: tuple[ObjectRef, ...]

    def __post_init__(self) -> None:
        members = tuple(sorted(self.members, key=lambda m: m.key))
        if not members or len(set(members)) != len(members):
            raise ValueError("groups require nonempty unique members")
        if any(member.scope != self.object.scope for member in members):
            raise ValueError("group members must share its scope")
        object.__setattr__(self, "members", members)


@dataclass(frozen=True, slots=True, kw_only=True)
class GroupAssignment:
    candidate_id: str
    group: GroupIdentity
    predecessors: tuple[ObjectRef, ...]
    transitions: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class GroupReconciliation:
    assignments: tuple[GroupAssignment, ...]
    retired: tuple[ObjectRef, ...]


def reconcile_groups(
    previous: Iterable[GroupIdentity],
    current: Iterable[GroupIdentity],
    *,
    scope: ScopeRef,
    namespace: str,
    generation: str,
) -> GroupReconciliation:
    """Assign durable group IDs using exact member overlap, never semantics.

    Current object IDs are temporary candidate labels. Greedy one-to-one matching
    ranks positive overlap by Jaccard, intersection size, old identity, then member
    keys. One split child can inherit an old ID; one predecessor survives a merge.
    All positive-overlap predecessors remain lineage. This is a deterministic
    heuristic, not maximum-weight matching and not evidence of content equality.

    A host-persisted unique generation token prevents retired identities from
    being resurrected accidentally. Repeat the same transaction with the same
    token for replay. Both snapshots must cover the complete selected partition.
    """
    old, new = tuple(previous), tuple(current)
    if not namespace.strip() or not generation.strip():
        raise ValueError("namespace and generation are required")
    for groups in (old, new):
        if len({g.object for g in groups}) != len(groups):
            raise ValueError("duplicate group identities")
        if any(
            g.object.scope != scope or g.object.namespace != namespace for g in groups
        ):
            raise ValueError("groups must share the requested namespace and scope")
    if len({g.members for g in new}) != len(new):
        raise ValueError("duplicate candidate memberships")
    inverted: dict[ObjectRef, list[int]] = defaultdict(list)
    for i, group in enumerate(old):
        for member in group.members:
            inverted[member].append(i)
    edges = []
    parents: dict[int, set[int]] = defaultdict(set)
    children: dict[int, set[int]] = defaultdict(set)
    for j, group in enumerate(new):
        counts = Counter(
            i for member in group.members for i in inverted.get(member, ())
        )
        for i, count in counts.items():
            parents[j].add(i)
            children[i].add(j)
            edges.append(
                (
                    -Fraction(count, len(old[i].members) + len(group.members) - count),
                    -count,
                    old[i].object.key,
                    tuple(m.key for m in group.members),
                    i,
                    j,
                )
            )
    matched: dict[int, int] = {}
    used: set[int] = set()
    for *_, i, j in sorted(edges):
        if i not in used and j not in matched:
            used.add(i)
            matched[j] = i
    assigned = []
    identities = {g.object for g in old}
    for j, group in enumerate(new):
        transitions = []
        if not parents[j]:
            transitions.append("created")
        elif len(parents[j]) == 1 and all(len(children[i]) == 1 for i in parents[j]):
            transitions.append("continued")
        if any(len(children[i]) > 1 for i in parents[j]):
            transitions.append("split")
        if len(parents[j]) > 1:
            transitions.append("merged")
        if j in matched:
            identity = old[matched[j]].object
        else:
            identity = ObjectRef(
                scope=scope,
                namespace=namespace,
                object_id="group:"
                + dependency_fingerprint(
                    [scope, namespace, generation, group.members]
                ).split(":", 1)[1],
            )
            if identity in identities:
                raise ValueError("generation reuses an existing group identity")
        identities.add(identity)
        assigned.append(
            GroupAssignment(
                candidate_id=group.object.object_id,
                group=GroupIdentity(object=identity, members=group.members),
                predecessors=tuple(
                    sorted((old[i].object for i in parents[j]), key=lambda r: r.key)
                ),
                transitions=tuple(transitions),
            )
        )
    return GroupReconciliation(
        assignments=tuple(sorted(assigned, key=lambda a: a.candidate_id)),
        retired=tuple(
            sorted(
                (old[i].object for i in range(len(old)) if i not in used),
                key=lambda r: r.key,
            )
        ),
    )
