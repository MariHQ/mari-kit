#!/usr/bin/env python3
"""Run reproducible public-corpus benchmarks against Mari implementations.

The runner never substitutes fixtures for a public corpus.  It verifies the
downloaded artifact, records per-query rankings, and writes an aggregate report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import time
import urllib.request
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from mari_components.evaluation import evaluate_retrieval
from mari_components.retrieval import BM25Index, DenseFlatIndex, HNSWIndex, IVFPQIndex

SCIFACT_URL = (
    "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip"
)
SCIFACT_MD5 = "5f7d1de60b170fc8027bb7898e2efca1"
LONGMEM_URL = (
    "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/"
    "main/longmemeval_s_cleaned.json"
)
LONGMEM_SHA256 = "d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442"
LONGMEM_EVALUATOR_COMMIT = "9e0b455f4ef0e2ab8f2e582289761153549043fc"
TOKEN_PATTERN = re.compile(r"\w+")


def digest(path: Path, algorithm: str) -> str:
    checksum = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def download(url: str, path: Path, algorithm: str, expected: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temporary = path.with_suffix(path.suffix + ".part")
        urllib.request.urlretrieve(url, temporary)
        temporary.replace(path)
    observed = digest(path, algorithm)
    if observed != expected:
        raise RuntimeError(f"{path}: expected {expected}, observed {observed}")


def prepare(data_dir: Path) -> None:
    archive = data_dir / "scifact.zip"
    download(SCIFACT_URL, archive, "md5", SCIFACT_MD5)
    if not (data_dir / "scifact" / "corpus.jsonl").exists():
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(data_dir)
    download(
        LONGMEM_URL,
        data_dir / "longmemeval_s_cleaned.json",
        "sha256",
        LONGMEM_SHA256,
    )


def percentile(values: list[float], percent: int) -> float:
    return float(np.percentile(np.asarray(values), percent)) if values else 0.0


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
    ).strip()


def environment() -> dict[str, Any]:
    repository = Path(__file__).resolve().parents[1]
    status = subprocess.check_output(
        ["git", "status", "--porcelain"], text=True
    ).splitlines()
    source_changes = [
        line for line in status if not line[3:].startswith("benchmarks/results/")
    ]
    return {
        "mari_commit": commit(),
        "source_worktree_dirty": bool(source_changes),
        "runner_sha256": digest(Path(__file__), "sha256"),
        "index_implementation_sha256": digest(
            repository / "src/mari_components/retrieval/indexes.py", "sha256"
        ),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
    }


def timed_search(search: Any) -> tuple[Any, float]:
    start = time.perf_counter_ns()
    value = search()
    return value, (time.perf_counter_ns() - start) / 1_000_000


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def scifact_retrieval(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    root = data_dir / "scifact"
    documents = {
        row["_id"]: f"{row.get('title', '')}\n{row.get('text', '')}".strip()
        for row in load_jsonl(root / "corpus.jsonl")
    }
    queries = {row["_id"]: row["text"] for row in load_jsonl(root / "queries.jsonl")}
    qrels: dict[str, dict[str, float]] = {}
    lines = (root / "qrels" / "test.tsv").read_text().splitlines()
    for line in lines[1:]:
        query_id, document_id, score = line.split("\t")
        qrels.setdefault(query_id, {})[document_id] = float(score)

    started = time.perf_counter()
    index = BM25Index(documents)
    build_seconds = time.perf_counter() - started
    cases: list[dict[str, Any]] = []
    latency: list[float] = []
    at_10, at_100 = [], []
    for query_id in sorted(qrels):
        hits, elapsed = timed_search(
            lambda q=queries[query_id]: index.search(q, limit=100)
        )
        ranked = [hit.document_id for hit in hits]
        score_10 = evaluate_retrieval(ranked, qrels[query_id], k=10)
        relevant = {key for key, value in qrels[query_id].items() if value > 0}
        recall_100 = len(relevant & set(ranked[:100])) / len(relevant)
        latency.append(elapsed)
        at_10.append(score_10)
        at_100.append(recall_100)
        cases.append(
            {
                "query_id": query_id,
                "latency_ms": elapsed,
                "ranked_ids": ranked,
                "relevance": qrels[query_id],
                "ndcg_at_10": score_10.ndcg,
                "mrr_at_10": score_10.reciprocal_rank,
                "recall_at_100": recall_100,
            }
        )
    report = {
        "benchmark": "beir-scifact-retrieval",
        "dataset": {
            "artifact": SCIFACT_URL,
            "artifact_md5": SCIFACT_MD5,
            "split": "test",
            "documents": len(documents),
            "queries": len(cases),
        },
        "system": {
            "retriever": "mari_components.retrieval.BM25Index",
            "k1": 1.2,
            "b": 0.75,
        },
        "metrics": {
            "ndcg_at_10": mean([score.ndcg for score in at_10]),
            "mrr_at_10": mean([score.reciprocal_rank for score in at_10]),
            "recall_at_10": mean([score.recall for score in at_10]),
            "recall_at_100": mean(at_100),
            "build_seconds": build_seconds,
            "query_latency_ms_p50": percentile(latency, 50),
            "query_latency_ms_p95": percentile(latency, 95),
        },
    }
    return report, cases


def hashed_vector(text: str, dimension: int) -> list[float]:
    values = np.zeros(dimension, dtype=np.float32)
    counts = Counter(TOKEN_PATTERN.findall(text.casefold()))
    for token, count in counts.items():
        token_hash = hashlib.sha256(token.encode()).digest()
        position = int.from_bytes(token_hash[:4], "big") % dimension
        sign = 1.0 if token_hash[4] & 1 else -1.0
        values[position] += sign * (1.0 + math.log(count))
    norm = np.linalg.norm(values)
    if norm:
        values /= norm
    return values.tolist()


def scifact_indexes(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    root = data_dir / "scifact"
    all_documents = {
        row["_id"]: f"{row.get('title', '')}\n{row.get('text', '')}".strip()
        for row in load_jsonl(root / "corpus.jsonl")
    }
    all_queries = {
        row["_id"]: row["text"] for row in load_jsonl(root / "queries.jsonl")
    }
    qrels: dict[str, set[str]] = {}
    lines = (root / "qrels" / "test.tsv").read_text().splitlines()
    for line in lines[1:]:
        query_id, document_id, score = line.split("\t")
        if float(score) > 0:
            qrels.setdefault(query_id, set()).add(document_id)
    selected_queries = sorted(qrels)[:64]
    required = {doc for query_id in selected_queries for doc in qrels[query_id]}
    selected_documents = (
        sorted(required)
        + [doc for doc in sorted(all_documents) if doc not in required][
            : 512 - len(required)
        ]
    )
    dimension = 128
    vectors = {
        doc: hashed_vector(all_documents[doc], dimension) for doc in selected_documents
    }
    query_vectors = {
        query: hashed_vector(all_queries[query], dimension)
        for query in selected_queries
    }

    indexes: dict[str, tuple[Any, dict[str, Any]]] = {}
    build_times: dict[str, float] = {}
    for name, constructor, config in (
        (
            "dense-flat",
            lambda: DenseFlatIndex(vectors, metric="cosine"),
            {"metric": "cosine"},
        ),
        (
            "hnsw",
            lambda: HNSWIndex(vectors, metric="cosine", m=16),
            {"metric": "cosine", "m": 16, "ef_search": 64},
        ),
        (
            "ivf-pq",
            lambda: IVFPQIndex(
                vectors, partitions=32, subquantizers=8, codebook_size=16
            ),
            {
                "metric": "l2",
                "partitions": 32,
                "probes": 8,
                "subquantizers": 8,
                "codebook_size": 16,
            },
        ),
    ):
        started = time.perf_counter()
        index = constructor()
        build_times[name] = time.perf_counter() - started
        indexes[name] = index, config

    exact: dict[str, list[str]] = {}
    for query_id in selected_queries:
        exact[query_id] = [
            hit.document_id
            for hit in indexes["dense-flat"][0].search(
                query_vectors[query_id], limit=10
            )
        ]
    cases: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}
    for name, (index, config) in indexes.items():
        latency: list[float] = []
        recalls: list[float] = []
        corpus_recalls: list[float] = []
        for query_id in selected_queries:
            kwargs = {"limit": 10}
            if name == "hnsw":
                kwargs["ef_search"] = 64
            elif name == "ivf-pq":
                kwargs["probes"] = 8
            hits, elapsed = timed_search(
                lambda i=index, q=query_vectors[query_id], kw=kwargs: i.search(q, **kw)
            )
            ranked = [hit.document_id for hit in hits]
            recall = len(set(ranked) & set(exact[query_id])) / 10
            corpus_recall = len(set(ranked) & qrels[query_id]) / len(qrels[query_id])
            latency.append(elapsed)
            recalls.append(recall)
            corpus_recalls.append(corpus_recall)
            cases.append(
                {
                    "index": name,
                    "query_id": query_id,
                    "latency_ms": elapsed,
                    "ranked_ids": ranked,
                    "exact_top_10": exact[query_id],
                    "ann_recall_at_10": recall,
                    "corpus_recall_at_10": corpus_recall,
                }
            )
        summaries[name] = {
            "config": config,
            "build_seconds": build_times[name],
            "ann_recall_at_10": mean(recalls),
            "corpus_recall_at_10": mean(corpus_recalls),
            "query_latency_ms_p50": percentile(latency, 50),
            "query_latency_ms_p95": percentile(latency, 95),
        }
    report = {
        "benchmark": "beir-scifact-indexes",
        "dataset": {
            "artifact": SCIFACT_URL,
            "artifact_md5": SCIFACT_MD5,
            "split": "test",
            "documents": len(selected_documents),
            "queries": len(selected_queries),
            "selection": "64 lexicographically first judged queries; all relevant documents plus lexicographic fill to 512",
        },
        "encoder": {
            "name": "signed-sha256-feature-hashing",
            "dimension": dimension,
            "purpose": "index-only comparison; corpus relevance is diagnostic, not a semantic encoder claim",
        },
        "metrics": summaries,
    }
    return report, cases


def session_text(session: list[dict[str, Any]], date: str) -> str:
    turns = "\n".join(f"{turn['role']}: {turn['content']}" for turn in session)
    return f"date: {date}\n{turns}"


def longmem_metrics(ranked: list[str], relevant: set[str], k: int) -> dict[str, float]:
    """Match LongMemEval's released session-level evaluator exactly."""

    observed = ranked[:k]
    recalled = set(observed)
    gains = [1.0 if identifier in relevant else 0.0 for identifier in observed]
    ideal = [1.0] * min(len(relevant), k) + [0.0] * max(0, k - len(relevant))

    def dcg(values: list[float]) -> float:
        if not values:
            return 0.0
        return values[0] + sum(
            value / math.log2(rank) for rank, value in enumerate(values[1:], 2)
        )

    ideal_dcg = dcg(ideal)
    return {
        "recall_any": float(bool(recalled & relevant)),
        "recall_all": float(relevant <= recalled),
        "evidence_coverage": len(recalled & relevant) / len(relevant),
        "ndcg_any": dcg(gains) / ideal_dcg if ideal_dcg else 0.0,
    }


def longmemeval_retrieval(
    data_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = data_dir / "longmemeval_s_cleaned.json"
    rows = json.loads(path.read_text())
    cases: list[dict[str, Any]] = []
    latency: list[float] = []
    metric_names = ("recall_any", "recall_all", "evidence_coverage", "ndcg_any")
    scores = {k: {metric: [] for metric in metric_names} for k in (1, 5, 10)}
    by_type: dict[str, dict[int, dict[str, list[float]]]] = {}
    skipped = 0
    build_seconds = 0.0
    for row in rows:
        relevant = set(row["answer_session_ids"])
        if "_abs" in row["question_id"] or not relevant:
            skipped += 1
            continue
        documents = {
            identifier: session_text(session, date)
            for identifier, session, date in zip(
                row["haystack_session_ids"],
                row["haystack_sessions"],
                row["haystack_dates"],
                strict=True,
            )
        }
        started = time.perf_counter()
        index = BM25Index(documents)
        build_seconds += time.perf_counter() - started
        hits, elapsed = timed_search(
            lambda i=index, question=row["question"]: i.search(question, limit=10)
        )
        ranked = [hit.document_id for hit in hits]
        type_scores = by_type.setdefault(
            row["question_type"],
            {k: {metric: [] for metric in metric_names} for k in (1, 5, 10)},
        )
        case_metrics: dict[str, float] = {}
        for k in (1, 5, 10):
            measured = longmem_metrics(ranked, relevant, k)
            for metric, value in measured.items():
                scores[k][metric].append(value)
                type_scores[k][metric].append(value)
                case_metrics[f"{metric}_at_{k}"] = value
        latency.append(elapsed)
        cases.append(
            {
                "question_id": row["question_id"],
                "question_type": row["question_type"],
                "latency_ms": elapsed,
                "ranked_session_ids": ranked,
                "answer_session_ids": sorted(relevant),
                **case_metrics,
            }
        )
    report = {
        "benchmark": "longmemeval-s-session-retrieval",
        "dataset": {
            "artifact": LONGMEM_URL,
            "artifact_sha256": LONGMEM_SHA256,
            "split": "cleaned-s",
            "questions_total": len(rows),
            "questions_scored": len(cases),
            "abstention_questions_skipped": skipped,
            "official_evaluator_commit": LONGMEM_EVALUATOR_COMMIT,
        },
        "system": {
            "retriever": "mari_components.retrieval.BM25Index",
            "granularity": "session",
            "session_key": "timestamp plus role-prefixed turns",
            "k1": 1.2,
            "b": 0.75,
        },
        "metrics": {
            **{
                f"{metric}_at_{k}": mean(scores[k][metric])
                for k in (1, 5, 10)
                for metric in metric_names
            },
            "mean_index_build_ms": build_seconds * 1000 / len(cases),
            "query_latency_ms_p50": percentile(latency, 50),
            "query_latency_ms_p95": percentile(latency, 95),
            "by_question_type": {
                kind: {
                    f"{metric}_at_{k}": mean(values[k][metric])
                    for k in (1, 5, 10)
                    for metric in metric_names
                }
                | {"queries": len(values[1]["recall_all"])}
                for kind, values in sorted(by_type.items())
            },
        },
    }
    return report, cases


def write_run(
    output_dir: Path, report: dict[str, Any], cases: list[dict[str, Any]]
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "environment": environment(),
        **report,
    }
    stem = report["benchmark"]
    (output_dir / f"{stem}.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    with (output_dir / f"{stem}.cases.jsonl").open("w") as stream:
        for case in cases:
            stream.write(json.dumps(case, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "suite",
        choices=("prepare", "scifact", "indexes", "longmemeval", "all"),
        nargs="?",
        default="all",
    )
    parser.add_argument("--data-dir", type=Path, default=Path("benchmarks/data"))
    parser.add_argument("--output-dir", type=Path, default=Path("benchmarks/results"))
    args = parser.parse_args()
    prepare(args.data_dir)
    if args.suite == "prepare":
        return
    runners = {
        "scifact": scifact_retrieval,
        "indexes": scifact_indexes,
        "longmemeval": longmemeval_retrieval,
    }
    selected = runners if args.suite == "all" else {args.suite: runners[args.suite]}
    for runner in selected.values():
        report, cases = runner(args.data_dir)
        write_run(args.output_dir, report, cases)


if __name__ == "__main__":
    main()
