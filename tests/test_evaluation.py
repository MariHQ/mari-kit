from __future__ import annotations

import json

import pytest

from mari_components.evaluation import (
    boundary_metrics,
    classification_metrics,
    evaluate_retrieval,
    load_catalog,
    ndcg_at_k,
    set_metrics,
)


def test_retrieval_metrics_use_graded_qrels() -> None:
    result = evaluate_retrieval(["b", "a", "x"], {"a": 2, "b": 1}, k=3)

    assert result.precision == pytest.approx(2 / 3)
    assert result.recall == 1.0
    assert result.reciprocal_rank == 1.0
    assert result.ndcg == pytest.approx(
        ndcg_at_k(["b", "a", "x"], {"a": 2, "b": 1}, k=3)
    )
    assert result.ndcg < 1.0


def test_classification_metrics_macro_average() -> None:
    result = classification_metrics(["yes", "yes", "no"], ["yes", "no", "no"])

    assert result.accuracy == pytest.approx(2 / 3)
    assert result.macro_f1 == pytest.approx(2 / 3)
    assert result.support == 3


def test_load_catalog_and_filter_tasks(tmp_path) -> None:
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "corpora": [
                    {
                        "id": "example",
                        "name": "Example",
                        "tasks": ["retrieval"],
                        "metrics": ["ndcg@10"],
                        "homepage": "https://example.test",
                        "license": "CC0",
                        "access": "direct",
                    }
                ],
            }
        )
    )

    catalog = load_catalog(path)

    assert catalog["example"].name == "Example"
    assert catalog.for_task("retrieval") == (catalog["example"],)


def test_catalog_rejects_duplicate_ids(tmp_path) -> None:
    corpus = {
        "id": "same",
        "name": "Same",
        "tasks": [],
        "metrics": [],
        "homepage": "https://example.test",
        "license": "unknown",
        "access": "manual",
    }
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"schema_version": 1, "corpora": [corpus, corpus]}))

    with pytest.raises(ValueError, match="unique"):
        load_catalog(path)


def test_evidence_set_metrics_count_missing_and_extra_ids() -> None:
    result = set_metrics({"e1", "e2"}, {"e2", "wrong"})

    assert result.precision == 0.5
    assert result.recall == 0.5
    assert result.f1 == 0.5


def test_boundary_metrics_use_one_to_one_tolerant_matches() -> None:
    result = boundary_metrics([10, 20], [9, 10, 22], tolerance=1)

    assert result.true_positive == 1
    assert result.false_positive == 2
    assert result.false_negative == 1
