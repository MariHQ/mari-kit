#!/usr/bin/env python3
"""Evaluate generic ranked JSONL against embedded graded relevance judgments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mari_components.evaluation import evaluate_retrieval


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("--k", type=int, default=10)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.run.read_text().splitlines() if line.strip()]
    if not rows:
        raise SystemExit("run contains no queries")
    scores = [evaluate_retrieval(row["ranked_ids"], row["relevance"], k=args.k) for row in rows]
    report = {
        "queries": len(scores), "k": args.k,
        "precision": sum(score.precision for score in scores) / len(scores),
        "recall": sum(score.recall for score in scores) / len(scores),
        "mrr": sum(score.reciprocal_rank for score in scores) / len(scores),
        "ndcg": sum(score.ndcg for score in scores) / len(scores),
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
