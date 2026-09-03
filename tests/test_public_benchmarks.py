from pathlib import Path

from benchmarks.run_public import hashed_vector, longmem_metrics
from benchmarks.verify_results import verify


def test_longmem_metrics_match_released_contract() -> None:
    ranked = ["distractor", "evidence-a", "evidence-b"]
    metrics = longmem_metrics(ranked, {"evidence-a", "evidence-b"}, 2)

    assert metrics == {
        "recall_any": 1.0,
        "recall_all": 0.0,
        "evidence_coverage": 0.5,
        "ndcg_any": 0.5,
    }


def test_feature_hash_is_deterministic_and_normalized() -> None:
    first = hashed_vector("retrieval evidence evidence", 32)
    second = hashed_vector("retrieval evidence evidence", 32)

    assert first == second
    assert abs(sum(value * value for value in first) - 1.0) < 1e-6


def test_committed_benchmark_aggregates_match_cases() -> None:
    verify(Path("benchmarks/results"))
