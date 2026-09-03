from __future__ import annotations

import json

import pytest

from mari_components.evaluation import (
    classification_metrics,
    evaluate_retrieval,
    load_catalog,
    ndcg_at_k,
)


def test_retrieval_metrics_use_graded_qrels() -> None:
    result = evaluate_retrieval(["b", "a", "x"], {"a": 2, "b": 1}, k=3)

    assert result.precision == pytest.approx(2 / 3)
    assert result.recall == 1.0
    assert result.reciprocal_rank == 1.0
    assert result.ndcg == pytest.approx(ndcg_at_k(["b", "a", "x"], {"a": 2, "b": 1}, k=3))
    assert result.ndcg < 1.0


def test_classification_metrics_macro_average() -> None:
    result = classification_metrics(["yes", "yes", "no"], ["yes", "no", "no"])

    assert result.accuracy == pytest.approx(2 / 3)
    assert result.macro_f1 == pytest.approx(2 / 3)
    assert result.support == 3


def test_load_catalog_and_filter_tasks(tmp_path) -> None:
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "corpora": [{
            "id": "example", "name": "Example", "tasks": ["retrieval"],
            "metrics": ["ndcg@10"], "homepage": "https://example.test",
            "license": "CC0", "access": "direct",
        }],
    }))

    catalog = load_catalog(path)

    assert catalog["example"].name == "Example"
    assert catalog.for_task("retrieval") == (catalog["example"],)


def test_catalog_rejects_duplicate_ids(tmp_path) -> None:
    corpus = {
        "id": "same", "name": "Same", "tasks": [], "metrics": [],
        "homepage": "https://example.test", "license": "unknown", "access": "manual",
    }
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"schema_version": 1, "corpora": [corpus, corpus]}))

    with pytest.raises(ValueError, match="unique"):
        load_catalog(path)
