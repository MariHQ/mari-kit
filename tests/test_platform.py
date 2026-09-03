import datetime as dt

import pytest

from mari_components.knowledge import Activity, KnowledgeArtifact, KnowledgeScope
from mari_components.platform import (
    InMemoryArtifactStore,
    KnowledgeEvent,
    MetricObjective,
    ObjectiveDirection,
    Pipeline,
    Stage,
    compile_configurations,
    replay_projection,
)


def test_pipeline_records_success_and_stops_dependents_after_failure() -> None:
    pipeline = Pipeline(
        stages=(
            Stage(
                name="double",
                version="1",
                transform=lambda values: (value * 2 for value in values),
            ),
            Stage(
                name="fail",
                version="1",
                transform=lambda _values: (_ for _ in ()).throw(
                    RuntimeError("bad input")
                ),
            ),
            Stage(name="unreached", version="1", transform=lambda values: values),
        )
    )
    result = pipeline.run([2])

    assert not result.succeeded
    assert [row.name for row in result.trace] == ["double", "fail"]
    assert result.outputs == ()


def test_projection_replay_requires_contiguous_generations() -> None:
    events = [
        KnowledgeEvent(event_id="a", generation=1, kind="add", payload={"value": 2}),
        KnowledgeEvent(event_id="b", generation=2, kind="add", payload={"value": 3}),
    ]
    build = replay_projection(
        0, events, projector=lambda state, event: state + event.payload["value"]
    )

    assert build.state == 5
    assert build.generation == 2
    assert build.build_id.startswith("sha256:")


def test_compiler_rejects_constraint_violations_before_utility() -> None:
    result = compile_configurations(
        [{"quality": 0.9, "latency": 100}, {"quality": 0.8, "latency": 10}],
        evaluate=lambda config: config,
        objectives=[
            MetricObjective(
                name="quality", direction=ObjectiveDirection.MAXIMIZE, minimum=0.85
            ),
            MetricObjective(
                name="latency", direction=ObjectiveDirection.MINIMIZE, weight=0.001
            ),
        ],
    )

    assert result.configuration["quality"] == 0.9
    assert (
        len([candidate for candidate in result.candidates if candidate.feasible]) == 1
    )


def test_reference_store_enforces_scope_revision_and_time_travel() -> None:
    store = InMemoryArtifactStore()
    scope = KnowledgeScope(tenant="acme")
    activity = Activity(identifier="rules/v1", implementation="rules")
    first = KnowledgeArtifact(
        artifact_id="policy",
        revision="v1",
        value="30 days",
        scope=scope,
        recorded_at=dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
        generated_by=activity,
    )
    second = KnowledgeArtifact(
        artifact_id="policy",
        revision="v2",
        value="14 days",
        scope=scope,
        recorded_at=dt.datetime(2025, 2, 1, tzinfo=dt.UTC),
        generated_by=activity,
        supersedes=("policy@v1",),
    )
    store.commit(first, expected_revision=None)
    store.commit(second, expected_revision="v1")

    assert store.get("policy", scope=scope) == second
    assert (
        store.at_time(
            "policy", scope=scope, known_at=dt.datetime(2025, 1, 15, tzinfo=dt.UTC)
        )
        == first
    )
    assert store.get("policy", scope=KnowledgeScope(tenant="other")) is None
    with pytest.raises(RuntimeError, match="expected"):
        store.commit(second, expected_revision="v1")
