#!/usr/bin/env python3
"""Recompute aggregate quality metrics from committed per-case benchmark records."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def mean(rows: list[dict[str, Any]], field: str) -> float:
    return sum(float(row[field]) for row in rows) / len(rows)


def close(observed: float, expected: float) -> None:
    if abs(observed - expected) > 1e-12:
        raise AssertionError(f"aggregate mismatch: {observed} != {expected}")


def load_cases(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    if not rows:
        raise AssertionError(f"{path} has no cases")
    return rows


def verify_scifact(results: Path) -> None:
    report = json.loads((results / "beir-scifact-retrieval.json").read_text())
    rows = load_cases(results / "beir-scifact-retrieval.cases.jsonl")
    assert len(rows) == report["dataset"]["queries"] == 300
    assert len({row["query_id"] for row in rows}) == len(rows)
    for case_field, report_field in (
        ("ndcg_at_10", "ndcg_at_10"),
        ("mrr_at_10", "mrr_at_10"),
        ("recall_at_100", "recall_at_100"),
    ):
        close(mean(rows, case_field), report["metrics"][report_field])


def verify_indexes(results: Path) -> None:
    report = json.loads((results / "beir-scifact-indexes.json").read_text())
    rows = load_cases(results / "beir-scifact-indexes.cases.jsonl")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["index"])].append(row)
    for name, cases in grouped.items():
        assert len(cases) == report["dataset"]["queries"] == 64
        close(
            mean(cases, "ann_recall_at_10"),
            report["metrics"][name]["ann_recall_at_10"],
        )
        close(
            mean(cases, "corpus_recall_at_10"),
            report["metrics"][name]["corpus_recall_at_10"],
        )


def verify_longmem(results: Path) -> None:
    report = json.loads((results / "longmemeval-s-session-retrieval.json").read_text())
    rows = load_cases(results / "longmemeval-s-session-retrieval.cases.jsonl")
    assert len(rows) == report["dataset"]["questions_scored"] == 470
    assert len({row["question_id"] for row in rows}) == len(rows)
    for k in (1, 5, 10):
        for metric in ("recall_any", "recall_all", "evidence_coverage", "ndcg_any"):
            field = f"{metric}_at_{k}"
            close(mean(rows, field), report["metrics"][field])


def declared_suites(path: Path = Path("benchmarks/suites.json")) -> tuple[str, ...]:
    catalog = json.loads(path.read_text())
    return tuple(str(row["id"]) for row in catalog["suites"])


def case_identity(row: dict[str, Any]) -> object | None:
    for field in (
        "case_id",
        "query_id",
        "question_id",
        "document_id",
        "test",
        "fingerprint",
    ):
        if field in row:
            return row[field]
    return None


def verify_declared_suites(results: Path) -> tuple[int, int]:
    suites = declared_suites()
    missing: list[str] = []
    case_total = 0
    for suite in suites:
        report_path = results / f"{suite}.json"
        cases_path = results / f"{suite}.cases.jsonl"
        if not report_path.exists() or not cases_path.exists():
            missing.append(suite)
            continue

        report = json.loads(report_path.read_text())
        rows = load_cases(cases_path)
        assert report["schema_version"] == 2
        assert report["suite"] == suite
        assert report["evaluation_type"]
        assert report["system"]["implementation"]
        assert report["metrics"]
        assert report["limitations"]
        assert report["reproduce"]
        assert report["environment"]["mari_commit"]
        assert report["environment"]["runner_sha256"]
        assert len(rows) == report["dataset"]["cases"]

        identities = [case_identity(row) for row in rows]
        if all(value is not None for value in identities):
            assert len(set(map(str, identities))) == len(rows), suite
        case_total += len(rows)

    if missing:
        raise AssertionError(f"missing result artifacts for: {', '.join(missing)}")
    return len(suites), case_total


def verify(results: Path) -> tuple[int, int]:
    verify_scifact(results)
    verify_indexes(results)
    verify_longmem(results)
    return verify_declared_suites(results)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "results", type=Path, nargs="?", default=Path("benchmarks/results")
    )
    args = parser.parse_args()
    suites, cases = verify(args.results)
    print(f"verified {suites} research reports and {cases} per-case records")


if __name__ == "__main__":
    main()
