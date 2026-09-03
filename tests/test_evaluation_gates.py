import datetime as dt

from mari_components.evaluation import (
    EvaluationRun,
    GateMode,
    MetricGate,
    regression_gate,
)


def test_regression_gate_reports_every_hard_constraint() -> None:
    report = regression_gate(
        {"recall": 0.79, "leakage": 0},
        baseline={"recall": 0.8},
        gates=[
            MetricGate(metric="recall", mode=GateMode.NO_REGRESSION, tolerance=0.02),
            MetricGate(metric="leakage", mode=GateMode.AT_MOST, value=0),
        ],
    )
    assert report.passed
    assert len(report.checks) == 2


def test_evaluation_run_keeps_reproduction_identity() -> None:
    run = EvaluationRun(
        run_id="run-1",
        corpus_id="beir",
        corpus_revision="sha256:data",
        split="test",
        mari_revision="git:abc",
        started_at=dt.datetime.now(dt.UTC),
        metrics={"ndcg@10": 0.5},
        configuration={"index": "bm25"},
        seed=7,
    )
    assert run.metrics["ndcg@10"] == 0.5
