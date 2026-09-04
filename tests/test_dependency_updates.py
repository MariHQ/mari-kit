from dataclasses import replace
from graphlib import CycleError

import pytest

from examples.quickstarts.dependency_updates import materialize, scenario
from mari_components import (
    DependencyKey,
    DependencyStamp,
    DerivationSpec,
    ObjectRef,
    ScopeRef,
    UpdateAction,
    dependency_fingerprint,
    materialization_receipt,
    plan_dependency_updates,
)
from mari_components.documents import (
    align_atoms,
    atom_collection_stamp,
    atom_dependencies,
    parse_markdown,
    plan_atom_refresh,
    semantic_atoms,
)
from mari_components.retrieval import RetrievalUnit, RevisionBM25Index


def key(name, *, tenant="acme", aspect="content"):
    return DependencyKey(
        object=ObjectRef(
            namespace="test", object_id=name, scope=ScopeRef(tenant=tenant)
        ),
        aspect=aspect,
    )


def stamp(name, value, **kwargs):
    return DependencyStamp(
        dependency=key(name, **kwargs), fingerprint=dependency_fingerprint(value)
    )


def spec(name, inputs, **kwargs):
    return DerivationSpec(
        output=key(name), inputs=tuple(inputs), implementation="test:v1", **kwargs
    )


def test_upstream_change_waits_for_actual_output_and_can_stop_propagation():
    first = stamp("source", "old wording")
    summary = spec("summary", [first.dependency])
    answer = spec("answer", [summary.output])
    summarized = materialization_receipt(
        summary, [first], output_fingerprint="same-meaning"
    )
    answered = materialization_receipt(
        answer, [summarized.output], output_fingerprint="answer-v1"
    )
    changed = stamp("source", "new wording")
    pending = plan_dependency_updates(
        sources=[changed],
        derivations=[answer, summary],
        materializations=[answered, summarized],
    )
    assert [(row.output, row.action) for row in pending.updates] == [
        (summary.output, UpdateAction.REBUILD),
        (answer.output, UpdateAction.WAIT),
    ]
    assert {row.dependency for row in pending.available} == {first.dependency}
    assert pending.ready[0].inputs == (changed,)
    # Only a receipt from completed work can make either output available.
    completed = materialization_receipt(
        summary, pending.ready[0].inputs, output_fingerprint="same-meaning"
    )
    stable = plan_dependency_updates(
        sources=[changed],
        derivations=[summary, answer],
        materializations=[completed, answered],
    )
    assert stable.reusable == (summary.output, answer.output)
    different = replace(
        completed, output=replace(completed.output, fingerprint="different-meaning")
    )
    final = plan_dependency_updates(
        sources=[changed],
        derivations=[summary, answer],
        materializations=[different, answered],
    )
    assert tuple(row.output for row in final.ready) == (answer.output,)


def test_missing_source_blocks_entire_chain_even_with_cached_outputs():
    root = stamp("source", "v1")
    left = spec("left", [root.dependency])
    right = spec("right", [left.output])
    receipt = materialization_receipt(left, [root], output_fingerprint="left-v1")
    plan = plan_dependency_updates(
        sources=[], derivations=[left, right], materializations=[receipt]
    )
    assert [row.action for row in plan.updates] == [UpdateAction.BLOCKED] * 2
    assert plan.updates[0].dependencies == (root.dependency,)
    assert plan.updates[1].dependencies == (left.output,)
    assert plan.available == ()


def test_policy_change_does_not_reembed_text_but_withholds_projection():
    text = stamp("source", "refunds")
    access = stamp("source", "employee", aspect="access")
    vector = spec("vector", [text.dependency])
    projection = spec("projection", [vector.output, access.dependency])
    embedded = materialization_receipt(vector, [text], output_fingerprint="vector")
    projected = materialization_receipt(
        projection, [embedded.output, access], output_fingerprint="projection"
    )
    revoked = stamp("source", "restricted", aspect="access")
    plan = plan_dependency_updates(
        sources=[text, revoked],
        derivations=[projection, vector],
        materializations=[projected, embedded],
    )
    assert plan.reusable == (vector.output,)
    assert plan.ready[0].output == projection.output
    assert plan.ready[0].dependencies == (access.dependency,)


@pytest.mark.parametrize(
    "change", ["implementation", "configuration", "order", "remove", "add"]
)
def test_recipe_and_input_membership_changes_invalidate(change):
    a, b, c = stamp("a", "A"), stamp("b", "B"), stamp("c", "C")
    before = spec("out", [a.dependency, b.dependency], configuration={"model": "v1"})
    receipt = materialization_receipt(before, [a, b], output_fingerprint="out")
    after = {
        "implementation": replace(before, implementation="test:v2"),
        "configuration": replace(before, configuration={"model": "v2"}),
        "order": replace(before, inputs=(b.dependency, a.dependency)),
        "remove": replace(before, inputs=(a.dependency,)),
        "add": replace(before, inputs=(a.dependency, b.dependency, c.dependency)),
    }[change]
    plan = plan_dependency_updates(
        sources=[a, b, c], derivations=[after], materializations=[receipt]
    )
    assert plan.ready[0].output == after.output


def test_scopes_cannot_supply_each_others_inputs():
    a = stamp("source", "same", tenant="a")
    b = stamp("source", "same", tenant="b")
    consumer = spec("out", [a.dependency])
    plan = plan_dependency_updates(sources=[b], derivations=[consumer])
    assert plan.updates[0].action is UpdateAction.BLOCKED


def test_invalid_graphs_and_conflicting_receipts_are_rejected():
    a, b = spec("a", [key("b")]), spec("b", [key("a")])
    with pytest.raises(CycleError):
        plan_dependency_updates(sources=[], derivations=[a, b])
    source = stamp("source", "v1")
    with pytest.raises(ValueError, match="conflicting"):
        plan_dependency_updates(sources=[source, stamp("source", "v2")], derivations=[])
    consumer = spec("out", [source.dependency])
    with pytest.raises(ValueError, match="one producer"):
        plan_dependency_updates(sources=[source], derivations=[consumer, consumer])
    with pytest.raises(ValueError, match="one producer"):
        plan_dependency_updates(sources=[stamp("out", "value")], derivations=[consumer])
    with pytest.raises(ValueError, match="in order"):
        materialization_receipt(consumer, [], output_fingerprint="out")
    receipt = materialization_receipt(consumer, [source], output_fingerprint="out")
    with pytest.raises(ValueError, match="unique"):
        plan_dependency_updates(
            sources=[source],
            derivations=[consumer],
            materializations=[receipt, receipt],
        )
    assert plan_dependency_updates(
        sources=[], derivations=[], materializations=[receipt]
    ).retired == (consumer.output,)


def test_long_graph_is_iterative_and_independent_input_order_is_deterministic():
    source = stamp("source", "v1")
    chain = [spec("0", [source.dependency])]
    for index in range(1, 1500):
        chain.append(spec(str(index), [chain[-1].output]))
    forward = plan_dependency_updates(sources=[source], derivations=chain)
    reverse = plan_dependency_updates(sources=[source], derivations=reversed(chain))
    assert forward == reverse
    assert len(forward.ready) == 1
    assert len(forward.updates) == 1500


SOURCE = ObjectRef(
    namespace="document", object_id="policy", scope=ScopeRef(tenant="acme")
)


def atoms(text, revision="v1"):
    return semantic_atoms(
        parse_markdown(text, artifact_id="policy", revision=revision).values[0]
    )


def test_atom_identity_connects_retrieval_evidence_and_dependency_inputs():
    atom = atoms("# Policy\n\nRefunds within 30 days.\n")[0]
    ref = atom.to_revision_ref(source=SOURCE)
    evidence = atom.located_evidence(source=SOURCE)
    unit = RetrievalUnit.from_atom(atom, source=SOURCE)
    assert unit.ref.to_revision_ref() == ref == evidence.ref
    assert unit.text == evidence.quote == atom.text
    index = RevisionBM25Index({ref: unit.text})
    assert index.search("refunds", limit=1, allowed_refs={ref})[0].ref == ref
    assert index.search("refunds", limit=1, allowed_refs=set()) == ()
    dependencies = atom_dependencies(atom, source=SOURCE)
    assert dependencies.revision == DependencyStamp.from_revision(ref)
    with pytest.raises(ValueError, match="must match"):
        atom_dependencies(atom, source=replace(SOURCE, object_id="wrong"))


def test_moving_atom_reuses_content_but_changes_context_and_binding():
    before = atoms("# Old heading\n\nRefunds within 30 days.\n")[0]
    after = atoms("# New heading\n\nRefunds within 30 days.\n", "v2")[0]
    old, new = (
        atom_dependencies(before, source=SOURCE),
        atom_dependencies(after, source=SOURCE),
    )
    assert old.content == new.content
    assert old.context != new.context
    assert old.binding != new.binding
    assert old.revision != new.revision


def test_normalized_alignment_is_not_proof_of_identical_embedding_input():
    before = atoms("# Policy\n\nRefunds within 30 days.\n")
    after = atoms("# Policy\n\nRefunds  within 30 days.\n", "v2")
    assert before[0].content_hash == after[0].content_hash
    plan = plan_atom_refresh(align_atoms(before, after))
    assert plan.reuse_raw_embeddings == ()
    assert plan.reuse_contextual_embeddings == ()
    assert plan.embed_raw_atom_ids == (after[0].atom_id,)
    assert plan.embed_contextual_atom_ids == (after[0].atom_id,)
    assert (
        atom_dependencies(before[0], source=SOURCE).content
        != atom_dependencies(after[0], source=SOURCE).content
    )


def test_membership_detects_insert_delete_reorder_but_not_revision_only_changes():
    before = atoms("# Policy\n\nRefunds within 30 days.\n\nContact support.\n")
    initial = atom_collection_stamp(before, source=SOURCE)
    revision_only = tuple(replace(atom, source_revision="v2") for atom in before)
    assert atom_collection_stamp(revision_only, source=SOURCE) == initial
    for changed in (before[:1], (), tuple(reversed(before))):
        assert atom_collection_stamp(changed, source=SOURCE) != initial
    after = atoms(
        "# Policy\n\nRefunds within 30 days.\n\nContact support.\n\nExceptions apply.\n"
    )
    assert atom_collection_stamp(after, source=SOURCE) != initial
    with pytest.raises(ValueError, match="unique"):
        atom_collection_stamp([before[0], before[0]], source=SOURCE)
    with pytest.raises(ValueError, match="one source revision"):
        atom_collection_stamp([before[0], revision_only[1]], source=SOURCE)


def test_configuration_is_frozen_and_fingerprints_reject_nonfinite_values():
    config = {"model": {"version": "v1"}}
    derivation = spec("out", [], configuration=config)
    fingerprint = derivation.fingerprint
    config["model"]["version"] = "v2"
    assert derivation.fingerprint == fingerprint
    with pytest.raises(ValueError, match="finite"):
        dependency_fingerprint(float("nan"))


def test_incremental_event_sequence_matches_clean_rebuild_across_consumers():
    base = "# Policy\n\nRefunds within 30 days.\n\nContact support.\n"
    versions = (
        (base, "v1", "allowed", "fixture:v1", 2),
        (base, "v2", "allowed", "fixture:v1", 0),
        (base.replace("Policy", "Terms"), "v3", "allowed", "fixture:v1", 0),
        (base.replace("30", "14"), "v4", "allowed", "fixture:v1", 1),
        (base.replace("30", "14"), "v4", "denied", "fixture:v1", 0),
        (base.replace("30", "14"), "v4", "denied", "fixture:v2", 2),
        ("# Policy\n\nContact support.\n", "v5", "allowed", "fixture:v2", 0),
        (
            "# Policy\n\nContact support.\n\nContact support.\n",
            "v6",
            "allowed",
            "fixture:v2",
            0,
        ),
        ("# Policy\n", "v7", "allowed", "fixture:v2", 0),
    )
    receipts, values = {}, {}
    for text, revision, policy, model, expected_vectors in versions:
        current = scenario(text, revision, policy=policy, model=model)
        rebuilt = materialize(current, receipts, values)
        clean_receipts, clean_values = {}, {}
        materialize(current, clean_receipts, clean_values)
        assert sum(key.aspect == "raw_vector" for key in rebuilt) == expected_vectors
        # Old history may remain in storage, but only current outputs are exposed.
        plan = plan_dependency_updates(
            sources=current.sources,
            derivations=current.specs,
            materializations=receipts.values(),
        )
        assert set(plan.reusable) == set(clean_values)
        assert all(
            values[key] == value and receipts[key] == clean_receipts[key]
            for key, value in clean_values.items()
        )
        assert materialize(current, receipts, values) == ()
        units = {unit.ref.to_revision_ref(): unit.text for unit in current.units}
        index = RevisionBM25Index(units)
        hits = index.search(
            "refunds",
            limit=10,
            allowed_refs=set(units) if policy == "allowed" else set(),
        )
        assert all(hit.ref.revision == revision for hit in hits)
        if policy == "denied":
            assert hits == ()


def test_failed_build_cannot_publish_a_receipt_or_release_dependents():
    current = scenario("# Policy\n\nRefunds within 30 days.\n", "v1")
    vector = next(
        item.output for item in current.specs if item.output.aspect == "raw_vector"
    )
    original = current.builders[vector]

    def fail():
        raise RuntimeError("embedding service unavailable")

    current.builders[vector] = fail
    receipts, values = {}, {}
    with pytest.raises(RuntimeError, match="unavailable"):
        materialize(current, receipts, values)
    assert vector not in receipts
    plan = plan_dependency_updates(
        sources=current.sources,
        derivations=current.specs,
        materializations=receipts.values(),
    )
    assert (
        next(
            item for item in plan.updates if item.output.aspect == "search_projection"
        ).action
        is UpdateAction.WAIT
    )
    current.builders[vector] = original
    materialize(current, receipts, values)
    assert materialize(current, receipts, values) == ()
