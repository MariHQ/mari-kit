import json
from pathlib import Path


def test_every_completed_paper_has_a_benchmark_suite() -> None:
    suites = json.loads(Path("benchmarks/suites.json").read_text())
    covered = {paper for suite in suites["suites"] for paper in suite["papers"]}
    completed = tuple(Path("research/papers/completed").glob("*.pdf"))
    unmatched = [
        path.name
        for path in completed
        if not any(path.name.startswith(f"{paper}-") for paper in covered)
    ]

    assert not unmatched


def test_every_suite_references_catalogued_corpora_and_unique_ids() -> None:
    suites = json.loads(Path("benchmarks/suites.json").read_text())["suites"]
    corpora = {
        corpus["id"]
        for corpus in json.loads(Path("benchmarks/catalog.json").read_text())["corpora"]
    }

    assert len({suite["id"] for suite in suites}) == len(suites)
    assert all(
        suite["api"] and suite["papers"] and suite["metrics"] for suite in suites
    )
    assert all(set(suite["corpora"]) <= corpora for suite in suites)


def test_every_declared_suite_has_committed_result_artifacts() -> None:
    suites = json.loads(Path("benchmarks/suites.json").read_text())["suites"]
    results = Path("benchmarks/results")
    missing = [
        suffix
        for suite in suites
        for suffix in (f"{suite['id']}.json", f"{suite['id']}.cases.jsonl")
        if not (results / suffix).exists()
    ]

    assert missing == []
