import random
from dataclasses import replace
from graphlib import CycleError

import pytest

from mari_components import (
    CountReducer,
    DeltaAggregate,
    DependencyIndex,
    DependencyKey,
    DependencyStamp,
    DerivationSpec,
    GroupIdentity,
    LexicalStatisticsReducer,
    MembershipReducer,
    ObjectRef,
    ScopeRef,
    SelectionSpec,
    UpdateAction,
    WeightedVectorReducer,
    complete_selection,
    dependency_fingerprint,
    materialization_receipt,
    plan_dependency_updates,
    plan_selection,
    reconcile_groups,
)

SCOPE = ScopeRef(tenant="acme", space="support")


def obj(name, namespace="test"):
    return ObjectRef(scope=SCOPE, namespace=namespace, object_id=name)


def key(name):
    return DependencyKey(object=obj(name))


def stamp(name, value):
    return DependencyStamp(dependency=key(name), fingerprint=str(value))


def spec(name, *inputs):
    return DerivationSpec(
        output=key(name), inputs=tuple(key(i) for i in inputs), implementation="v1"
    )


def test_index_frontier_and_unchanged_cutoff():
    specs = (spec("a", "source"), spec("b", "a"), spec("other", "unrelated"))
    sources = (stamp("source", 1), stamp("unrelated", 1))
    index = DependencyIndex(sources=sources, derivations=specs)
    receipts = []
    while index.plan().ready:
        for task in index.plan().ready:
            recipe = next(s for s in specs if s.output == task.output)
            receipt = materialization_receipt(
                recipe, task.inputs, output_fingerprint="constant"
            )
            receipts.append(receipt)
            index.apply(materializations=(receipt,))
    assert index.apply(sources=(stamp("source", 2),)) == (key("a"), key("b"))
    task = index.plan().ready[0]
    receipt = materialization_receipt(
        specs[0], task.inputs, output_fingerprint="constant"
    )
    assert index.apply(materializations=(receipt,)) == (key("a"), key("b"))
    assert not index.plan().ready
    assert index.apply(sources=(stamp("source", 2),)) == ()
    target = index.plan(targets=(key("b"),))
    assert {u.output for u in target.updates} == {key("a"), key("b")}
    assert {s.dependency for s in target.available} == {
        key("source"),
        key("a"),
        key("b"),
    }
    with pytest.raises(ValueError):
        index.plan(targets=(key("unknown"),))


@pytest.mark.parametrize("seed", range(6))
def test_index_random_deltas_equal_snapshot_planner(seed):
    rng = random.Random(seed)
    sources = {key(f"s{i}"): stamp(f"s{i}", 0) for i in range(5)}
    names = [f"s{i}" for i in range(5)]
    specs = {}
    for i in range(25):
        recipe = spec(f"d{i}", *rng.sample(names, rng.randint(0, min(3, len(names)))))
        specs[recipe.output] = recipe
        names.append(f"d{i}")
    receipts = {}
    index = DependencyIndex(sources=sources.values(), derivations=specs.values())
    for tick in range(100):
        ready = index.plan().ready
        action = rng.randrange(5)
        if action == 0 and ready:
            task = rng.choice(ready)
            receipt = materialization_receipt(
                specs[task.output],
                task.inputs,
                output_fingerprint=dependency_fingerprint(
                    [s.fingerprint for s in task.inputs]
                ),
            )
            receipts[task.output] = receipt
            index.apply(materializations=(receipt,))
        elif action == 1:
            s = stamp(f"s{rng.randrange(5)}", tick % 3)
            sources[s.dependency] = s
            index.apply(sources=(s,))
        elif action == 2:
            k = key(f"s{rng.randrange(5)}")
            sources.pop(k, None)
            index.apply(removed_sources=(k,))
        elif action == 3 and receipts:
            k = rng.choice(list(receipts))
            receipts.pop(k)
            index.apply(evicted_outputs=(k,))
        else:
            k = rng.choice(list(specs))
            recipe = replace(specs[k], implementation=f"v{tick}")
            specs[k] = recipe
            index.apply(derivations=(recipe,))
        assert index.plan() == plan_dependency_updates(
            sources=sources.values(),
            derivations=specs.values(),
            materializations=receipts.values(),
        )


def test_index_topology_retirement_cycle_and_atomic_validation():
    a = spec("a", "s")
    index = DependencyIndex(sources=(stamp("s", 1),), derivations=(a,))
    before = index.plan()
    with pytest.raises(CycleError):
        index.apply(derivations=(spec("a", "b"), spec("b", "a")))
    assert index.plan() == before
    with pytest.raises(ValueError):
        index.apply(sources=(stamp("s", 2), stamp("s", 3)))
    assert index.plan() == before
    with pytest.raises(ValueError):
        index.apply(sources=(stamp("a", 2),))
    receipt = materialization_receipt(
        a, before.ready[0].inputs, output_fingerprint="a1"
    )
    index.apply(materializations=(receipt,))
    index.apply(removed_derivations=(key("a"),))
    assert index.plan().retired == (key("a"),)
    index.apply(derivations=(a,))
    assert index.plan().reusable == (key("a"),)


def test_index_large_unrelated_graph_visits_one_output():
    index = DependencyIndex(
        sources=(stamp(f"s{i}", 1) for i in range(2000)),
        derivations=(spec(f"d{i}", f"s{i}") for i in range(2000)),
    )
    assert index.apply(sources=(stamp("s1000", 2),)) == (key("d1000"),)


def test_delayed_receipt_cannot_release_newer_input_snapshot():
    recipe = spec("a", "s")
    index = DependencyIndex(
        sources=(stamp("s", 1),), derivations=(recipe, spec("b", "a"))
    )
    old_task = index.plan().ready[0]
    delayed = materialization_receipt(recipe, old_task.inputs, output_fingerprint="old")
    index.apply(sources=(stamp("s", 2),), materializations=(delayed,))
    assert index.plan().ready[0].inputs == (stamp("s", 2),)
    assert index.plan().updates[1].action is UpdateAction.WAIT
    assert key("a") not in {s.dependency for s in index.plan().available}


def test_selection_notices_nonwinners_insertions_deletions_and_recipe():
    rule = SelectionSpec(
        object=obj("selection"), implementation="topk:v1", configuration={"limit": 1}
    )
    plan = plan_selection(rule, (stamp("a", 1), stamp("b", 1)))
    receipt = complete_selection(plan, (key("a"),))
    assert (
        plan_selection(rule, reversed(plan.candidates), previous=receipt).update.action
        is UpdateAction.REUSE
    )
    changed = plan_selection(rule, (stamp("a", 1), stamp("b", 2)), previous=receipt)
    assert changed.update.action is UpdateAction.REBUILD
    unchanged = complete_selection(changed, (key("a"),))
    assert unchanged.materialization.output == receipt.materialization.output
    assert unchanged.consumer_inputs == receipt.consumer_inputs
    inserted = plan_selection(rule, (*plan.candidates, stamp("c", 1)), previous=receipt)
    assert inserted.update.action is UpdateAction.REBUILD
    assert (
        complete_selection(inserted, (key("c"),)).materialization.output
        != receipt.materialization.output
    )
    assert (
        plan_selection(
            replace(rule, implementation="v2"), plan.candidates, previous=receipt
        ).update.action
        is UpdateAction.REBUILD
    )
    assert (
        complete_selection(plan_selection(rule, (), previous=receipt), ()).selected
        == ()
    )
    with pytest.raises(ValueError):
        complete_selection(plan, (key("absent"),))
    with pytest.raises(ValueError):
        complete_selection(plan, (key("a"), key("a")))
    foreign = DependencyStamp(
        dependency=DependencyKey(
            object=ObjectRef(
                scope=ScopeRef(tenant="other"), namespace="x", object_id="a"
            )
        ),
        fingerprint="1",
    )
    with pytest.raises(ValueError):
        plan_selection(rule, (foreign,))


def test_selection_order_selected_revisions_and_policy_are_distinct():
    rule = SelectionSpec(object=obj("selection"), implementation="v1")
    first = plan_selection(
        rule, (stamp("a", 1), stamp("b", 1)), dependencies=(stamp("policy", 1),)
    )
    old = complete_selection(first, (key("a"), key("b")))
    new = complete_selection(first, (key("b"), key("a")))
    assert new.materialization.output != old.materialization.output
    changed = plan_selection(
        rule,
        (stamp("a", 2), stamp("b", 1)),
        dependencies=(stamp("policy", 1),),
        previous=old,
    )
    new = complete_selection(changed, (key("a"), key("b")))
    assert new.materialization.output == old.materialization.output
    assert new.consumer_inputs != old.consumer_inputs
    revoked = plan_selection(
        rule, changed.candidates, dependencies=(stamp("policy", 2),), previous=new
    )
    assert revoked.update.action is UpdateAction.REBUILD


def group(name, *members):
    return GroupIdentity(
        object=obj(name, "group"), members=tuple(obj(m) for m in members)
    )


def reconcile(old, new, generation="1"):
    return reconcile_groups(
        old, new, scope=SCOPE, namespace="group", generation=generation
    )


def test_group_continuation_split_merge_retirement_and_replay():
    old = (group("stable", "a", "b", "c"), group("unrelated", "z"))
    new = (group("left", "a", "b"), group("right", "c"))
    result = reconcile(old, new)
    by_id = {a.candidate_id: a for a in result.assignments}
    assert by_id["left"].group.object == old[0].object
    assert by_id["right"].group.object != old[0].object
    assert all(a.transitions == ("split",) for a in result.assignments)
    assert result.retired == (old[1].object,)
    assert reconcile(reversed(old), reversed(new)) == result
    merged = reconcile(
        tuple(a.group for a in result.assignments),
        (group("merged", "a", "b", "c"),),
        "2",
    )
    assert merged.assignments[0].transitions == ("merged",)
    assert len(merged.assignments[0].predecessors) == 2
    assert merged.assignments[0].group.object == old[0].object
    assert len(merged.retired) == 1
    assert reconcile((), (group("new", "a"),), "1") != reconcile(
        (), (group("new", "a"),), "2"
    )
    assert reconcile(old, ()).retired == tuple(
        sorted((g.object for g in old), key=lambda r: r.key)
    )


@pytest.mark.parametrize(
    "reducer,value1,value2",
    [
        (CountReducer(), "a", "b"),
        (
            WeightedVectorReducer(),
            {"vector": [0.1, 2.3], "weight": 0.3},
            {"vector": [0.2, 3.7], "weight": 0.1},
        ),
        (LexicalStatisticsReducer(), {"a": 2, "b": 1}, {"b": 3}),
        (MembershipReducer(), ["x", "y"], ["y", "z"]),
    ],
)
def test_aggregate_edit_sequences_match_clean_rebuild(reducer, value1, value2):
    aggregate = DeltaAggregate(reducer, scope=SCOPE)
    values = {}
    rng = random.Random(0)
    for _ in range(100):
        k = key(str(rng.randrange(8)))
        if rng.randrange(3):
            value = rng.choice([value1, value2])
            values[k] = value
            aggregate.apply(((k, value),))
        else:
            values.pop(k, None)
            aggregate.apply(removed=(k,))
        rebuilt = DeltaAggregate(reducer, scope=SCOPE)
        rebuilt.apply(values.items())
        assert aggregate.value == rebuilt.value
        assert aggregate.stamp(key("output")) == rebuilt.stamp(key("output"))
        assert aggregate.contributions == rebuilt.contributions
    aggregate.apply(removed=tuple(values))
    assert aggregate.value == DeltaAggregate(reducer, scope=SCOPE).value


def test_aggregate_rejects_bad_inputs_atomically_and_freezes_values():
    aggregate = DeltaAggregate(WeightedVectorReducer(), scope=SCOPE)
    value = {"vector": [1, 2]}
    aggregate.apply(((key("a"), value),))
    value["vector"][0] = 99
    assert aggregate.value["centroid"] == (1, 2)
    before = aggregate.value
    for invalid in (
        {"vector": [3]},
        {"vector": [1, 2], "weight": 0},
        {"vector": [float("nan"), 2]},
    ):
        with pytest.raises(ValueError):
            aggregate.apply(((key("b"), invalid),))
        assert aggregate.value == before
    with pytest.raises(ValueError):
        aggregate.apply(((key("a"), {"vector": [2, 3]}),), removed=(key("a"),))
