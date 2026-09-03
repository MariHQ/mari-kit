#!/usr/bin/env python3
"""Recompute aggregate quality metrics from committed per-case benchmark records."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def mean(rows: list[dict[str, object]], field: str) -> float:
    return sum(float(row[field]) for row in rows) / len(rows)


def close(observed: float, expected: float) -> None:
    if abs(observed - expected) > 1e-12:
        raise AssertionError(f"aggregate mismatch: {observed} != {expected}")


def load_cases(path: Path) -> list[dict[str, object]]:
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
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
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


def verify(results: Path) -> None:
    verify_scifact(results)
    verify_indexes(results)
    verify_longmem(results)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "results", type=Path, nargs="?", default=Path("benchmarks/results")
    )
    args = parser.parse_args()
    verify(args.results)
    print("verified 3 reports and 962 case records")


if __name__ == "__main__":
    main()
