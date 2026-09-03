from mari_components.trajectories import TrajectoryStep, learn_procedure


def step(ordinal: int, tool: str, **arguments: str) -> TrajectoryStep:
    return TrajectoryStep(ordinal, tool, "test", arguments, "", True)


def test_procedure_mines_common_successful_subsequence_and_stable_args() -> None:
    candidate = learn_procedure(
        {
            "run-b": [
                step(0, "search", query="refund"),
                step(1, "debug"),
                step(2, "answer", format="short"),
            ],
            "run-a": [
                step(0, "search", query="refund"),
                step(1, "answer", format="long"),
            ],
        },
        intent="answer refund question",
    )

    assert [value.tool for value in candidate.steps] == ["search", "answer"]
    assert dict(candidate.steps[0].arguments) == {"query": "refund"}
    assert dict(candidate.steps[1].arguments) == {}
    assert candidate.source_trajectory_ids == ("run-a", "run-b")
