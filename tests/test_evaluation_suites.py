import json

import pytest

from mari_components.evaluation import load_suite_catalog


def test_suite_catalog_can_select_every_suite_for_a_paper() -> None:
    catalog = load_suite_catalog("benchmarks/suites.json")

    sparsecl = catalog.get("sparsecl")
    assert sparsecl.api == "rank_sparse_contradictions"
    assert catalog.for_paper("2406.10746") == (sparsecl,)


def test_suite_catalog_rejects_duplicate_ids(tmp_path) -> None:
    path = tmp_path / "suites.json"
    row = {
        "id": "same",
        "api": "run",
        "papers": ["paper"],
        "corpora": ["corpus"],
        "metrics": ["score"],
    }
    path.write_text(json.dumps({"schema_version": 1, "suites": [row, row]}))

    with pytest.raises(ValueError, match="unique"):
        load_suite_catalog(path)
