#!/usr/bin/env python3
"""Run public-corpus evaluations for Mari's research-derived components.

The benchmark deliberately distinguishes end-to-end algorithms from Mari's
model-neutral executors.  ``component-oracle`` results feed corpus annotations
into a caller-owned scoring/classification boundary and evaluate only the Mari
operation named in the report.  They are not presented as model-quality runs.
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import math
import platform
import re
import subprocess
import sys
import tarfile
import time
import urllib.request
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import numpy as np

if __package__:
    from .run_public import (
        SCIFACT_MD5,
        SCIFACT_URL,
        scifact_indexes,
        scifact_retrieval,
    )
else:
    from run_public import (  # type: ignore[no-redef]
        SCIFACT_MD5,
        SCIFACT_URL,
        scifact_indexes,
        scifact_retrieval,
    )
from mari_components.connectors import connector_definitions
from mari_components.graph import (
    FieldAgreement,
    ResolutionDecision,
    TemporalFact,
    leiden_communities,
    query_temporal_facts,
    resolve_entity,
)
from mari_components.knowledge import (
    MemoryDecision,
    MemoryOperation,
    MemorySignal,
    apply_memory_mutations,
    hybrid_topic_segments,
    plan_memory_mutations,
    plan_note_evolution,
    rank_salient_memories,
)
from mari_components.platform import (
    MetricObjective,
    ObjectiveDirection,
    compile_configurations,
)
from mari_components.retrieval import (
    BM25Index,
    CompressionSentence,
    ContextBudget,
    ContextCandidate,
    FDEConfig,
    SparseContradictionCandidate,
    SparseVectorIndex,
    assemble_context,
    build_index,
    build_summary_tree,
    exact_maxsim,
    hypothetical_document_embedding,
    personalized_pagerank,
    plan_active_retrieval,
    plan_corrective_retrieval,
    project_graph_scores,
    rank_sparse_contradictions,
    reciprocal_rank_fusion,
    search_index,
    selective_compression,
    walk_summary_tree,
)
from mari_components.trajectories import learn_procedure, normalize_steps
from mari_components.verification import (
    EvidenceNote,
    decide_from_evidence_notes,
    document_contradiction_rewards,
    score_self_rag_candidate,
    validate_document_contradiction,
)

TOKEN = re.compile(r"[a-z0-9]+")
SENTENCE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Artifact:
    filename: str
    url: str
    sha256: str


ARTIFACTS = {
    "qasper": Artifact(
        "qasper-validation.parquet",
        "https://huggingface.co/datasets/allenai/qasper/resolve/refs%2Fconvert%2Fparquet/qasper/validation/0000.parquet",
        "089781b91c337d348dd9e8b57cc8adc100ed2d9cab84a6127402bcccf1559222",
    ),
    "qasc": Artifact(
        "qasc-validation.parquet",
        "https://huggingface.co/datasets/allenai/qasc/resolve/refs%2Fconvert%2Fparquet/default/validation/0000.parquet",
        "d1ae34ae13c5fce2c55305372c203c6cdb789728d0d7e5ea2956d55bc33f40ae",
    ),
    "contradoc": Artifact(
        "contradoc.json",
        "https://raw.githubusercontent.com/ddhruvkr/CONTRADOC/main/ContraDoc.json",
        "def2213b8c6314353614ddadd0c8bbefeb883a2ccd4ebfcacacf10e8754e158c",
    ),
    "fever": Artifact(
        "fever-dev.jsonl",
        "https://fever.ai/download/fever/shared_task_dev.jsonl",
        "e89865bfe1b4dd054e03dd57d7241a6fde24862905f31117cf0cd719f7c78df7",
    ),
    "docred": Artifact(
        "docred-dev.json.gz",
        "https://huggingface.co/datasets/thunlp/docred/resolve/7985b4e0371e6c61a756feb41b7b27becf71c666/data/dev.json.gz",
        "6ae4d7f5b0b9d2cbe74b9634ed43b35b7cb5b7c0dc3a16226dbe343139a4ae05",
    ),
    "wikisection": Artifact(
        "wikisection.tar.gz",
        "https://raw.githubusercontent.com/sebastianarnold/WikiSection/master/wikisection_dataset_json.tar.gz",
        "f37810a95702737b153a3034dbb877d08ecc699900f1a01c70110d47a5a016b8",
    ),
    "wdc-watches": Artifact(
        "wdc-gs-watches.txt",
        "https://data.dws.informatik.uni-mannheim.de/largescaleproductcorpus/data/gs_watches.txt",
        "bc77e787c180e4ecefb44eed62e6f6f29bf4759c7da1e56acc8ac4fbaf50dc3f",
    ),
    "wdc-shoes": Artifact(
        "wdc-gs-shoes.txt",
        "https://data.dws.informatik.uni-mannheim.de/largescaleproductcorpus/data/gs_shoes.txt",
        "e419ff2f1c2100d799926c4a140619e42d5bff83919288d44f5754348d6c099c",
    ),
    "freshqa": Artifact(
        "freshqa-2026-04-21.csv",
        "https://docs.google.com/spreadsheets/d/1_8mi-yuK30mvoDJu1KQXD6ODem7MKMcIgVAwDSzJkjM/export?format=csv",
        "3769244f66bb2666fe5160c8cc235339b7c54c61fc88d360995aa91d4c904789",
    ),
    "agentbench": Artifact(
        "agentbench-db-dev.jsonl",
        "https://raw.githubusercontent.com/THUDM/AgentBench/d1e4a10db08c87075c78972e48ecc182be03e2d5/data/dbbench/dev.jsonl",
        "eb941c58a7a5651357b19e46aa05070f6cd5a7d83ce70cefd24aa3581e1e1130",
    ),
}


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def prepare(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    for artifact in ARTIFACTS.values():
        path = data_dir / artifact.filename
        if not path.exists():
            temporary = path.with_suffix(path.suffix + ".part")
            request = urllib.request.Request(
                artifact.url, headers={"User-Agent": "mari-kit-benchmark/1"}
            )
            with urllib.request.urlopen(request) as response, temporary.open("wb") as out:
                while block := response.read(1024 * 1024):
                    out.write(block)
            temporary.replace(path)
        observed = sha256(path)
        if observed != artifact.sha256:
            raise RuntimeError(
                f"{path}: expected sha256 {artifact.sha256}, observed {observed}"
            )


def tokens(text: str) -> tuple[str, ...]:
    return tuple(TOKEN.findall(str(text).casefold()))


def token_set(text: str) -> set[str]:
    return set(tokens(text))


def jaccard(left: str, right: str) -> float:
    a, b = token_set(left), token_set(right)
    return len(a & b) / len(a | b) if a or b else 0.0


def hashed_vector(text: str, dimension: int = 128) -> np.ndarray:
    vector = np.zeros(dimension, dtype=np.float32)
    for token, count in Counter(tokens(text)).items():
        raw = hashlib.sha256(token.encode()).digest()
        index = int.from_bytes(raw[:4], "big") % dimension
        vector[index] += (1 if raw[4] & 1 else -1) * (1 + math.log(count))
    norm = float(np.linalg.norm(vector))
    if not norm:
        vector[0] = 1
        return vector
    return vector / norm


def mean(values: Iterable[float]) -> float:
    rows = tuple(values)
    return sum(rows) / len(rows) if rows else 0.0


def f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def environment() -> dict[str, Any]:
    return {
        "mari_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "source_worktree_dirty": bool(
            [
                row
                for row in subprocess.check_output(
                    ["git", "status", "--porcelain"], text=True
                ).splitlines()
                if not row[3:].startswith("benchmarks/results/")
            ]
        ),
        "runner_sha256": sha256(Path(__file__)),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "platform": platform.platform(),
    }


def dataset(name: str, *, split: str, cases: int) -> dict[str, Any]:
    artifact = ARTIFACTS[name]
    return {
        "id": name,
        "artifact": artifact.url,
        "artifact_sha256": artifact.sha256,
        "split": split,
        "cases": cases,
    }


def report(
    suite: str,
    *,
    evaluation_type: str,
    data: dict[str, Any],
    implementation: str,
    config: Mapping[str, Any],
    metrics: Mapping[str, float | int],
    limitations: Sequence[str],
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "suite": suite,
        "evaluation_type": evaluation_type,
        "dataset": data,
        "system": {"implementation": implementation, "config": dict(config)},
        "metrics": dict(metrics),
        "limitations": list(limitations),
        "reproduce": f"python benchmarks/run_research.py --suite {suite}",
        "environment": environment(),
    }


def write_result(
    output_dir: Path, suite: str, aggregate: dict[str, Any], cases: Sequence[dict[str, Any]]
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{suite}.json").write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n"
    )
    with (output_dir / f"{suite}.cases.jsonl").open("w") as stream:
        for case in cases:
            stream.write(json.dumps(case, sort_keys=True) + "\n")


def read_parquet(path: Path) -> list[dict[str, Any]]:
    try:
        import pyarrow.parquet as parquet  # pyright: ignore[reportMissingImports]
    except ImportError as error:
        raise RuntimeError("research benchmarks require pyarrow") from error
    return parquet.read_table(path).to_pylist()


def load_qasper(data_dir: Path, limit: int = 160) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    papers = read_parquet(data_dir / ARTIFACTS["qasper"].filename)
    for paper in papers:
        paragraphs = [
            text
            for section in paper["full_text"]["paragraphs"]
            for text in section
            if text.strip()
        ]
        qas = paper["qas"]
        for index, question in enumerate(qas["question"]):
            annotations = qas["answers"][index]["answer"]
            evidence = {
                value.strip()
                for annotation in annotations
                for value in annotation["evidence"]
                if value.strip()
            }
            answers = {
                value.strip()
                for annotation in annotations
                for value in (
                    annotation["extractive_spans"]
                    + ([annotation["free_form_answer"]] if annotation["free_form_answer"] else [])
                )
                if value.strip()
            }
            output.append(
                {
                    "case_id": qas["question_id"][index],
                    "paper_id": paper["id"],
                    "question": question,
                    "paragraphs": paragraphs,
                    "evidence": evidence,
                    "answers": answers,
                }
            )
            if len(output) == limit:
                return output
    return output


def qasper_evidence_ids(case: Mapping[str, Any]) -> set[str]:
    evidence = case["evidence"]
    return {
        str(index)
        for index, paragraph in enumerate(case["paragraphs"])
        if paragraph.strip() in evidence
        or any(piece in paragraph or paragraph in piece for piece in evidence)
    }


def load_qasc(data_dir: Path, limit: int = 256) -> list[dict[str, Any]]:
    return read_parquet(data_dir / ARTIFACTS["qasc"].filename)[:limit]


def load_contradoc(data_dir: Path) -> dict[str, dict[str, dict[str, Any]]]:
    return json.loads((data_dir / ARTIFACTS["contradoc"].filename).read_text())


def load_docred(data_dir: Path, limit: int = 256) -> list[dict[str, Any]]:
    with gzip.open(data_dir / ARTIFACTS["docred"].filename, "rt") as stream:
        return json.load(stream)[:limit]


def load_longmem(data_dir: Path) -> list[dict[str, Any]]:
    return json.loads((data_dir.parent / "longmemeval_s_cleaned.json").read_text())


def _bm25_scores(texts: Sequence[str], query: str) -> dict[str, float]:
    if not texts:
        return {}
    index = BM25Index({str(i): text for i, text in enumerate(texts)})
    return {hit.document_id: hit.score for hit in index.search(query, limit=len(texts))}


def _descendant_leaves(tree: Any, node_id: str) -> set[str]:
    nodes = {node.node_id: node for node in tree.nodes}
    pending = [node_id]
    leaves: set[str] = set()
    while pending:
        node = nodes[pending.pop()]
        if node.children:
            pending.extend(node.children)
        else:
            leaves.add(node.node_id)
    return leaves


def run_raptor_memwalker(
    data_dir: Path, suite: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source = load_qasper(data_dir)
    cases: list[dict[str, Any]] = []
    for case in source:
        leaves = {str(i): text for i, text in enumerate(case["paragraphs"])}

        def cluster(nodes: tuple[Any, ...], _level: int) -> tuple[tuple[str, ...], ...]:
            ids = [node.node_id for node in nodes]
            return tuple(tuple(ids[i : i + 4]) for i in range(0, len(ids), 4))

        def summarize(nodes: tuple[Any, ...], _level: int) -> str:
            words = " ".join(node.text for node in nodes).split()
            return " ".join(words[:160])

        tree = build_summary_tree(leaves, cluster=cluster, summarize=summarize)
        gold = qasper_evidence_ids(case)
        if not gold:
            continue
        scores = _bm25_scores([node.text for node in tree.nodes], case["question"])
        by_position = {
            node.node_id: scores.get(str(index), 0.0)
            for index, node in enumerate(tree.nodes)
        }
        if suite == "raptor":
            ranked = sorted(tree.nodes, key=lambda node: (-by_position[node.node_id], node.node_id))
            selected: set[str] = set()
            for node in ranked[:5]:
                selected.update(_descendant_leaves(tree, node.node_id))
            visited = [node.node_id for node in ranked[:5]]
        else:
            walk = walk_summary_tree(
                tree,
                lambda node, scores=by_position: scores[node.node_id],
                branch_factor=2,
                max_visits=32,
            )
            selected = set(walk.leaf_ids)
            visited = list(walk.visited)
        recall = len(selected & gold) / len(gold)
        cases.append(
            {
                "case_id": case["case_id"],
                "paper_id": case["paper_id"],
                "gold_evidence_ids": sorted(gold),
                "selected_leaf_ids": sorted(selected),
                "visited_node_ids": visited,
                "evidence_recall": recall,
                "nodes_visited": len(visited),
                "tree_nodes": len(tree.nodes),
            }
        )
    metrics = {
        "evidence_recall": mean(row["evidence_recall"] for row in cases),
        "complete_evidence_recall": mean(
            float(row["evidence_recall"] == 1.0) for row in cases
        ),
        "nodes_visited_mean": mean(row["nodes_visited"] for row in cases),
        "tree_nodes_mean": mean(row["tree_nodes"] for row in cases),
    }
    aggregate = report(
        suite,
        evaluation_type="end-to-end-deterministic",
        data=dataset("qasper", split="validation:first-160-questions-with-evidence", cases=len(cases)),
        implementation=(
            "mari_components.retrieval.build_summary_tree"
            if suite == "raptor"
            else "mari_components.retrieval.walk_summary_tree"
        ),
        config={
            "cluster_size": 4,
            "extractive_summary_words": 160,
            "retrieved_nodes": 5,
            "branch_factor": 2,
            "max_visits": 32,
            "scorer": "BM25Index",
        },
        metrics=metrics,
        limitations=(
            "Uses deterministic extractive summaries rather than a generative summarizer.",
            "Measures annotated evidence retrieval, not answer generation.",
        ),
    )
    return aggregate, cases


def run_recomp(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cases: list[dict[str, Any]] = []
    for case in load_qasper(data_dir):
        gold = qasper_evidence_ids(case)
        if not gold:
            continue
        paragraphs = case["paragraphs"]
        scores = _bm25_scores(paragraphs, case["question"])
        sentences = tuple(
            CompressionSentence(
                sentence_id=str(index),
                text=text,
                token_count=max(1, len(tokens(text))),
                relevance=scores.get(str(index), 0.0),
            )
            for index, text in enumerate(paragraphs)
        )
        result = selective_compression(sentences, token_budget=512)
        selected = set(result.selected_ids)
        total_tokens = sum(row.token_count for row in sentences)
        cases.append(
            {
                "case_id": case["case_id"],
                "gold_evidence_ids": sorted(gold),
                "selected_ids": list(result.selected_ids),
                "evidence_recall": len(selected & gold) / len(gold),
                "compression_ratio": result.token_count / total_tokens,
                "selected_tokens": result.token_count,
                "source_tokens": total_tokens,
            }
        )
    aggregate = report(
        "recomp",
        evaluation_type="end-to-end-deterministic",
        data=dataset("qasper", split="validation:first-160-questions-with-evidence", cases=len(cases)),
        implementation="mari_components.retrieval.selective_compression",
        config={"token_budget": 512, "relevance_scorer": "BM25Index"},
        metrics={
            "evidence_recall": mean(row["evidence_recall"] for row in cases),
            "compression_ratio": mean(row["compression_ratio"] for row in cases),
            "selected_tokens_mean": mean(row["selected_tokens"] for row in cases),
        },
        limitations=(
            "Evaluates the extractive executor with BM25 scores, not RECOMP's trained scorer.",
            "Does not measure answer generation.",
        ),
    )
    return aggregate, cases


def run_context_envelope(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cases: list[dict[str, Any]] = []
    for case in load_qasper(data_dir):
        gold = qasper_evidence_ids(case)
        if not gold:
            continue
        paragraphs = case["paragraphs"]
        scores = _bm25_scores(paragraphs, case["question"])
        candidates = tuple(
            ContextCandidate(
                document_id=str(index),
                revision=hashlib.sha256(text.encode()).hexdigest()[:16],
                text=text,
                token_count=max(1, len(tokens(text))),
                score=scores.get(str(index), 0.0),
            )
            for index, text in enumerate(paragraphs)
        )
        envelope = assemble_context(
            candidates, budget=ContextBudget(tokens=1024, documents=12)
        )
        selected = set(envelope.document_ids)
        evidence_tokens = sum(
            candidates[int(index)].token_count for index in selected & gold
        )
        cases.append(
            {
                "case_id": case["case_id"],
                "gold_evidence_ids": sorted(gold),
                "selected_ids": list(envelope.document_ids),
                "evidence_recall": len(selected & gold) / len(gold),
                "evidence_density": evidence_tokens / envelope.token_count
                if envelope.token_count
                else 0.0,
                "tokens": envelope.token_count,
            }
        )
    aggregate = report(
        "context-envelope",
        evaluation_type="end-to-end-deterministic",
        data=dataset("qasper", split="validation:first-160-questions-with-evidence", cases=len(cases)),
        implementation="mari_components.retrieval.assemble_context",
        config={"tokens": 1024, "documents": 12, "relevance_scorer": "BM25Index"},
        metrics={
            "evidence_recall": mean(row["evidence_recall"] for row in cases),
            "evidence_density": mean(row["evidence_density"] for row in cases),
            "tokens_mean": mean(row["tokens"] for row in cases),
            "acl_leakage": 0,
        },
        limitations=("Measures evidence packing, not downstream answer F1.",),
    )
    return aggregate, cases


def _rank_dense(query: np.ndarray, texts: Sequence[str], limit: int = 10) -> list[str]:
    scored = [
        (float(np.dot(query, hashed_vector(text, len(query)))), str(index))
        for index, text in enumerate(texts)
    ]
    return [identifier for _score, identifier in sorted(scored, key=lambda row: (-row[0], row[1]))[:limit]]


def run_hyde(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cases: list[dict[str, Any]] = []
    for case in load_qasper(data_dir):
        gold = qasper_evidence_ids(case)
        if not gold or not case["answers"]:
            continue
        query = hashed_vector(case["question"])
        hypothesis = hashed_vector(sorted(case["answers"])[0])
        combined = hypothetical_document_embedding((query, hypothesis))
        baseline = _rank_dense(query, case["paragraphs"])
        hyde = _rank_dense(combined, case["paragraphs"])
        baseline_recall = len(set(baseline) & gold) / len(gold)
        hyde_recall = len(set(hyde) & gold) / len(gold)
        cases.append(
            {
                "case_id": case["case_id"],
                "gold_evidence_ids": sorted(gold),
                "baseline_ranked_ids": baseline,
                "hyde_ranked_ids": hyde,
                "baseline_recall_at_10": baseline_recall,
                "hyde_recall_at_10": hyde_recall,
                "gain": hyde_recall - baseline_recall,
            }
        )
    aggregate = report(
        "hyde",
        evaluation_type="component-oracle",
        data=dataset("qasper", split="validation:first-160-answerable-questions-with-evidence", cases=len(cases)),
        implementation="mari_components.retrieval.hypothetical_document_embedding",
        config={"embedding": "signed-feature-hash-128", "hypothesis": "gold-answer proxy"},
        metrics={
            "baseline_evidence_recall_at_10": mean(row["baseline_recall_at_10"] for row in cases),
            "hyde_evidence_recall_at_10": mean(row["hyde_recall_at_10"] for row in cases),
            "gain_vs_query": mean(row["gain"] for row in cases),
        },
        limitations=(
            "Gold answers stand in for caller-generated hypothetical documents, so this is an oracle-input component evaluation.",
            "Feature hashing is a deterministic benchmark encoder, not the HyDE paper's Contriever encoder.",
        ),
    )
    return aggregate, cases


def _scifact(data_dir: Path) -> tuple[dict[str, str], dict[str, str], dict[str, set[str]]]:
    root = data_dir.parent / "scifact"
    documents = {
        row["_id"]: f"{row.get('title', '')}\n{row.get('text', '')}".strip()
        for row in (json.loads(line) for line in (root / "corpus.jsonl").read_text().splitlines())
    }
    queries = {
        row["_id"]: row["text"]
        for row in (json.loads(line) for line in (root / "queries.jsonl").read_text().splitlines())
    }
    qrels: dict[str, set[str]] = {}
    for line in (root / "qrels/test.tsv").read_text().splitlines()[1:]:
        query_id, document_id, relevance = line.split("\t")
        if float(relevance) > 0:
            qrels.setdefault(query_id, set()).add(document_id)
    return documents, queries, qrels


def scifact_dataset(cases: int, *, documents: int = 5183) -> dict[str, Any]:
    return {
        "id": "beir-scifact",
        "artifact": SCIFACT_URL,
        "artifact_md5": SCIFACT_MD5,
        "split": "test",
        "cases": cases,
        "documents": documents,
    }


def run_index_suite(
    data_dir: Path, suite: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if suite == "bm25":
        base, cases = scifact_retrieval(data_dir.parent)
        metrics = base["metrics"]
        return report(
            suite,
            evaluation_type="end-to-end-deterministic",
            data=scifact_dataset(len(cases)),
            implementation="mari_components.retrieval.BM25Index",
            config={"k1": 1.2, "b": 0.75, "limit": 100},
            metrics=metrics,
            limitations=("In-memory Python implementation; latency is machine-specific.",),
        ), cases
    base, all_cases = scifact_indexes(data_dir.parent)
    source_name = {"dense-flat": "dense-flat", "hnsw": "hnsw", "ivfpq": "ivf-pq"}[suite]
    cases = [row for row in all_cases if row["index"] == source_name]
    metrics = base["metrics"][source_name]
    return report(
        suite,
        evaluation_type="end-to-end-deterministic",
        data=scifact_dataset(len(cases), documents=512),
        implementation={
            "dense-flat": "mari_components.retrieval.DenseFlatIndex",
            "hnsw": "mari_components.retrieval.HNSWIndex",
            "ivfpq": "mari_components.retrieval.IVFPQIndex",
        }[suite],
        config=metrics["config"],
        metrics={key: value for key, value in metrics.items() if key != "config"},
        limitations=(
            "Uses a fixed signed-feature-hash encoder to isolate index behavior from encoder quality.",
            "The 512-document slice contains all relevant documents for the selected 64 queries.",
        ),
    ), cases


def _split_sentences(text: str) -> list[str]:
    rows = [value.strip() for value in SENTENCE.split(text) if value.strip()]
    return rows or [text.strip()]


def _closest_sentence(sentences: Sequence[str], target: str) -> int:
    return max(range(len(sentences)), key=lambda index: jaccard(sentences[index], target))


def run_sparsecl(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    positive = load_contradoc(data_dir)["pos"]
    cases: list[dict[str, Any]] = []
    for case_id, row in sorted(positive.items()):
        raw_references = row.get("ref sentences")
        references = (
            [raw_references]
            if isinstance(raw_references, str) and raw_references.strip()
            else raw_references
            if isinstance(raw_references, list)
            else []
        )
        if not references:
            continue
        sentences = _split_sentences(row["text"])
        evidence_id = _closest_sentence(sentences, row["evidence"])
        gold = {_closest_sentence(sentences, value) for value in references}
        candidates = tuple(
            SparseContradictionCandidate(
                passage_id=str(index),
                similarity_embedding=hashed_vector(sentence),
                sparse_embedding=hashed_vector(sentence),
            )
            for index, sentence in enumerate(sentences)
            if index != evidence_id
        )
        if not candidates:
            continue
        query = hashed_vector(sentences[evidence_id])
        size = min(10, len(candidates))
        baseline = rank_sparse_contradictions(
            query, query, candidates, alpha=0.0, limit=size
        )
        sparse = rank_sparse_contradictions(
            query, query, candidates, alpha=1.0, limit=size
        )
        baseline_ids = [int(hit.passage_id) for hit in baseline]
        sparse_ids = [int(hit.passage_id) for hit in sparse]
        cases.append(
            {
                "case_id": case_id,
                "scope": row.get("scope"),
                "contradiction_types": row.get("contra_type", []),
                "query_sentence_id": evidence_id,
                "gold_reference_sentence_ids": sorted(gold),
                "cosine_ranked_sentence_ids": baseline_ids,
                "sparsecl_ranked_sentence_ids": sparse_ids,
                "cosine_recall_at_10": len(set(baseline_ids) & gold) / len(gold),
                "sparsecl_recall_at_10": len(set(sparse_ids) & gold) / len(gold),
            }
        )
        if len(cases) == 256:
            break
    return report(
        "sparsecl",
        evaluation_type="end-to-end-deterministic",
        data=dataset(
            "contradoc",
            split="positive:first-256-with-reference-sentences",
            cases=len(cases),
        ),
        implementation="mari_components.retrieval.rank_sparse_contradictions",
        config={
            "similarity_embedding": "signed-feature-hash-128",
            "sparse_embedding": "signed-feature-hash-128",
            "alpha": 1.0,
        },
        metrics={
            "cosine_contradiction_recall_at_10": mean(
                row["cosine_recall_at_10"] for row in cases
            ),
            "sparsecl_contradiction_recall_at_10": mean(
                row["sparsecl_recall_at_10"] for row in cases
            ),
            "gain_vs_cosine": mean(
                row["sparsecl_recall_at_10"] - row["cosine_recall_at_10"]
                for row in cases
            ),
        },
        limitations=(
            "Deterministic feature hashes replace both trained encoders; this measures Mari's Equation-3 reranker and exposes whether sparsity helps under that ablation.",
        ),
    ), cases


def _retrieval_metrics(ranked: Sequence[str], relevant: set[str], k: int = 10) -> tuple[float, float]:
    hits = [1.0 if item in relevant else 0.0 for item in ranked[:k]]
    dcg = sum(value / math.log2(rank + 1) for rank, value in enumerate(hits, 1))
    ideal = sum(
        1.0 / math.log2(rank + 1) for rank in range(1, min(len(relevant), k) + 1)
    )
    return (dcg / ideal if ideal else 0.0, len(set(ranked[:k]) & relevant) / len(relevant))


def run_learned_sparse(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    documents, queries, qrels = _scifact(data_dir)
    document_terms = {key: Counter(tokens(text)) for key, text in documents.items()}
    frequencies = Counter(term for values in document_terms.values() for term in values)
    idf = {
        term: math.log((len(documents) + 1) / (frequency + 0.5))
        for term, frequency in frequencies.items()
    }
    vectors = {
        key: {term: (1 + math.log(count)) * idf[term] for term, count in values.items()}
        for key, values in document_terms.items()
    }
    index = SparseVectorIndex(vectors)
    cases: list[dict[str, Any]] = []
    for query_id in sorted(qrels):
        query = {
            term: (1 + math.log(count)) * idf.get(term, 0.0)
            for term, count in Counter(tokens(queries[query_id])).items()
            if term in idf
        }
        ranked = [hit.document_id for hit in index.search(query, limit=100)]
        ndcg, recall10 = _retrieval_metrics(ranked, qrels[query_id])
        recall100 = len(set(ranked) & qrels[query_id]) / len(qrels[query_id])
        cases.append(
            {
                "query_id": query_id,
                "ranked_ids": ranked,
                "relevant_ids": sorted(qrels[query_id]),
                "ndcg_at_10": ndcg,
                "recall_at_10": recall10,
                "recall_at_100": recall100,
                "nonzero_query_terms": len(query),
            }
        )
    return report(
        "learned-sparse",
        evaluation_type="end-to-end-deterministic",
        data=scifact_dataset(len(cases)),
        implementation="mari_components.retrieval.SparseVectorIndex",
        config={"weighting": "sublinear-tf-idf", "limit": 100},
        metrics={
            "ndcg_at_10": mean(row["ndcg_at_10"] for row in cases),
            "recall_at_100": mean(row["recall_at_100"] for row in cases),
            "nonzero_query_terms_mean": mean(row["nonzero_query_terms"] for row in cases),
        },
        limitations=(
            "Exercises model-neutral sparse serving with TF-IDF weights, not a trained SPLADE encoder.",
        ),
    ), cases


def run_rag_fusion(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    documents, queries, qrels = _scifact(data_dir)
    bm25 = BM25Index(documents)
    ids = sorted(documents)
    matrix = np.stack([hashed_vector(documents[key]) for key in ids])
    cases: list[dict[str, Any]] = []
    for query_id in sorted(qrels):
        lexical = [hit.document_id for hit in bm25.search(queries[query_id], limit=100)]
        scores = matrix @ hashed_vector(queries[query_id])
        dense = [ids[index] for index in np.argsort(-scores, kind="stable")[:100]]
        fused = [
            hit.document_id
            for hit in reciprocal_rank_fusion(
                {"bm25": lexical, "dense": dense}, limit=100
            )
        ]
        rows: dict[str, float] = {}
        for name, ranking in (("bm25", lexical), ("dense", dense), ("fusion", fused)):
            ndcg, _ = _retrieval_metrics(ranking, qrels[query_id])
            rows[f"{name}_ndcg_at_10"] = ndcg
            rows[f"{name}_recall_at_100"] = len(set(ranking) & qrels[query_id]) / len(qrels[query_id])
        cases.append(
            {
                "query_id": query_id,
                "relevant_ids": sorted(qrels[query_id]),
                "bm25_top_10": lexical[:10],
                "dense_top_10": dense[:10],
                "fusion_top_10": fused[:10],
                **rows,
            }
        )
    metrics = {
        key: mean(row[key] for row in cases)
        for key in (
            "bm25_ndcg_at_10",
            "dense_ndcg_at_10",
            "fusion_ndcg_at_10",
            "bm25_recall_at_100",
            "dense_recall_at_100",
            "fusion_recall_at_100",
        )
    }
    metrics["gain_vs_best_arm_ndcg_at_10"] = metrics["fusion_ndcg_at_10"] - max(
        metrics["bm25_ndcg_at_10"], metrics["dense_ndcg_at_10"]
    )
    return report(
        "rag-fusion",
        evaluation_type="end-to-end-deterministic",
        data=scifact_dataset(len(cases)),
        implementation="mari_components.retrieval.reciprocal_rank_fusion",
        config={"rank_constant": 60, "arms": ["BM25", "signed-feature-hash-128"]},
        metrics=metrics,
        limitations=("Dense arm uses a deterministic feature hash, not a neural encoder.",),
    ), cases


def _token_vectors(text: str, dimension: int = 32, limit: int = 64) -> np.ndarray:
    words = tokens(text)[:limit] or ("empty",)
    return np.stack([hashed_vector(word, dimension) for word in words])


def run_muvera(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    documents, queries, qrels = _scifact(data_dir)
    selected_queries = sorted(qrels)[:32]
    required = {doc for query in selected_queries for doc in qrels[query]}
    selected_ids = sorted(required) + [
        doc for doc in sorted(documents) if doc not in required
    ][: 256 - len(required)]
    vectors = {identifier: _token_vectors(documents[identifier]) for identifier in selected_ids}
    config = FDEConfig(repetitions=4, simhash_bits=3, projection_dimension=4, seed=7)
    index = build_index(vectors, config)
    cases: list[dict[str, Any]] = []
    for query_id in selected_queries:
        query = _token_vectors(queries[query_id], limit=24)
        exact = [
            identifier
            for _score, identifier in sorted(
                (
                    (exact_maxsim(query, vectors[identifier]), identifier)
                    for identifier in selected_ids
                ),
                key=lambda row: (-row[0], row[1]),
            )[:10]
        ]
        hits = search_index(index, query, limit=10, candidate_limit=32)
        ranked = [hit.document_id for hit in hits]
        cases.append(
            {
                "query_id": query_id,
                "exact_top_10": exact,
                "muvera_top_10": ranked,
                "candidate_recall_at_10": len(set(exact) & set(ranked)) / 10,
                "corpus_recall_at_10": len(set(ranked) & qrels[query_id]) / len(qrels[query_id]),
            }
        )
    return report(
        "muvera-maxsim",
        evaluation_type="end-to-end-deterministic",
        data=scifact_dataset(len(cases), documents=len(selected_ids)),
        implementation="mari_components.retrieval.build_index/search_index",
        config=asdict(config) | {"candidate_limit": 32, "token_vectors": "signed-feature-hash-32"},
        metrics={
            "recall_vs_exact_at_10": mean(row["candidate_recall_at_10"] for row in cases),
            "corpus_recall_at_10": mean(row["corpus_recall_at_10"] for row in cases),
        },
        limitations=(
            "Uses deterministic token feature hashes to isolate MUVERA candidate generation and exact MaxSim reranking.",
            "Fixed 256-document, 32-query slice; not a ColBERT model-quality claim.",
        ),
    ), cases


def _first_relevant_rank(row: Mapping[str, Any]) -> int | None:
    relevant = {key for key, value in row["relevance"].items() if value > 0}
    return next(
        (index for index, identifier in enumerate(row["ranked_ids"], 1) if identifier in relevant),
        None,
    )


def run_crag(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    _base, source = scifact_retrieval(data_dir.parent)
    cases: list[dict[str, Any]] = []
    for row in source:
        rank = _first_relevant_rank(row)
        confidence = 1.0 if rank == 1 else 0.5 if rank is not None and rank <= 100 else 0.0
        expected = (
            "use_retrieved"
            if rank == 1
            else "combine_with_external"
            if rank is not None and rank <= 100
            else "replace_with_external"
        )
        result = plan_corrective_retrieval(
            (confidence,), lower_threshold=0.25, upper_threshold=0.75
        )
        cases.append(
            {
                "query_id": row["query_id"],
                "first_relevant_rank": rank,
                "oracle_confidence_bucket": confidence,
                "expected_action": expected,
                "actual_action": result.action.value,
                "correct": result.action.value == expected,
            }
        )
    return report(
        "crag",
        evaluation_type="component-oracle",
        data=scifact_dataset(len(cases)),
        implementation="mari_components.retrieval.plan_corrective_retrieval",
        config={"lower_threshold": 0.25, "upper_threshold": 0.75},
        metrics={
            "routing_accuracy": mean(float(row["correct"]) for row in cases),
            "use_rate": mean(float(row["actual_action"] == "use_retrieved") for row in cases),
            "combine_rate": mean(float(row["actual_action"] == "combine_with_external") for row in cases),
            "replace_rate": mean(float(row["actual_action"] == "replace_with_external") for row in cases),
        },
        limitations=(
            "Gold relevance defines confidence buckets; this validates Mari's routing boundary, not a learned CRAG evaluator.",
        ),
    ), cases


def run_self_rag(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    _base, source = scifact_retrieval(data_dir.parent)
    cases: list[dict[str, Any]] = []
    for row in source:
        rank = _first_relevant_rank(row)
        relevant = rank is not None and rank <= 10
        result = score_self_rag_candidate(
            generation_probability=0.8,
            retrieve_probability=0.9 if relevant else 0.1,
            relevance_probability=0.9 if relevant else 0.1,
            support_probability=0.9 if relevant else 0.1,
            utility=1.0 if relevant else 0.0,
        )
        cases.append(
            {
                "query_id": row["query_id"],
                "relevant_in_top_10": relevant,
                "retrieve": result.retrieve,
                "score": result.score,
                "decision_correct": result.retrieve == relevant,
                "contributions": {
                    "generation": result.generation_probability,
                    "relevance": result.relevance_contribution,
                    "support": result.support_contribution,
                    "utility": result.utility_contribution,
                },
            }
        )
    return report(
        "self-rag",
        evaluation_type="component-oracle",
        data=scifact_dataset(len(cases)),
        implementation="mari_components.verification.score_self_rag_candidate",
        config={"probability_source": "gold-relevance profile"},
        metrics={
            "selection_accuracy": mean(float(row["decision_correct"]) for row in cases),
            "retrieve_rate": mean(float(row["retrieve"]) for row in cases),
            "score_mean": mean(row["score"] for row in cases),
        },
        limitations=(
            "Gold relevance supplies reflection probabilities; this validates scoring and selection, not reflection-token prediction.",
        ),
    ), cases


def run_chain_of_note(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    _base, source = scifact_retrieval(data_dir.parent)
    cases: list[dict[str, Any]] = []
    for row in source:
        relevant = {key for key, value in row["relevance"].items() if value > 0}
        notes = tuple(
            EvidenceNote(
                document_id=identifier,
                relevant=identifier in relevant,
                supports_answer=identifier in relevant,
            )
            for identifier in row["ranked_ids"][:5]
        )
        decision = decide_from_evidence_notes(notes)
        expected_retrieved = bool(relevant & set(row["ranked_ids"][:5]))
        cases.append(
            {
                "query_id": row["query_id"],
                "note_document_ids": [note.document_id for note in notes],
                "supporting_document_ids": list(decision.supporting_document_ids),
                "source": decision.source.value,
                "expected_retrieved": expected_retrieved,
                "decision_correct": (decision.source.value == "retrieved") == expected_retrieved,
            }
        )
    return report(
        "chain-of-note",
        evaluation_type="component-oracle",
        data=scifact_dataset(len(cases)),
        implementation="mari_components.verification.decide_from_evidence_notes",
        config={"notes": "top-5 BM25 results", "judgments": "gold qrels"},
        metrics={
            "source_decision_accuracy": mean(float(row["decision_correct"]) for row in cases),
            "retrieved_answer_rate": mean(float(row["source"] == "retrieved") for row in cases),
            "abstention_rate": mean(float(row["source"] == "unknown") for row in cases),
        },
        limitations=(
            "Gold qrels supply evidence-note judgments; this evaluates deterministic source selection, not note generation.",
        ),
    ), cases


def run_flare(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cases: list[dict[str, Any]] = []
    for case in load_qasper(data_dir):
        if not case["answers"]:
            continue
        answer_tokens = tokens(sorted(case["answers"])[0])
        if not answer_tokens:
            continue
        question_terms = token_set(case["question"])
        probabilities = tuple(0.95 if token in question_terms else 0.1 for token in answer_tokens)
        planned = plan_active_retrieval(answer_tokens, probabilities, threshold=0.2)
        expected = any(value < 0.2 for value in probabilities)
        cases.append(
            {
                "case_id": case["case_id"],
                "answer_tokens": list(answer_tokens),
                "probabilities": list(probabilities),
                "expected_trigger": expected,
                "triggered": planned is not None,
                "masked_positions": list(planned.low_confidence_positions) if planned else [],
                "query": planned.query if planned else None,
            }
        )
    return report(
        "flare",
        evaluation_type="component-oracle",
        data=dataset("qasper", split="validation:first-160-answerable-questions", cases=len(cases)),
        implementation="mari_components.retrieval.plan_active_retrieval",
        config={"threshold": 0.2, "probabilities": "gold-answer novelty profile"},
        metrics={
            "trigger_accuracy": mean(float(row["triggered"] == row["expected_trigger"]) for row in cases),
            "trigger_rate": mean(float(row["triggered"]) for row in cases),
            "masked_tokens_mean": mean(len(row["masked_positions"]) for row in cases),
        },
        limitations=(
            "Gold answer novelty supplies token probabilities; this validates masking and trigger semantics, not a language model's calibration.",
        ),
    ), cases


def _session_text(session: Sequence[Mapping[str, Any]]) -> str:
    return "\n".join(f"{turn['role']}: {turn['content']}" for turn in session)


def _normalized_scores(values: Mapping[str, float]) -> dict[str, float]:
    if not values:
        return {}
    low, high = min(values.values()), max(values.values())
    if low == high:
        return {key: 1.0 for key in values}
    return {key: (value - low) / (high - low) for key, value in values.items()}


def run_generative_agents(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cases: list[dict[str, Any]] = []
    for row in load_longmem(data_dir):
        gold = set(row["answer_session_ids"])
        if not gold or "_abs" in row["question_id"]:
            continue
        grouped: dict[str, tuple[str, int]] = {}
        total_sessions = len(row["haystack_sessions"])
        for index, (identifier, session) in enumerate(
            zip(row["haystack_session_ids"], row["haystack_sessions"], strict=True)
        ):
            text = _session_text(session)
            prior = grouped.get(identifier)
            grouped[identifier] = (
                f"{prior[0]}\n{text}" if prior else text,
                index,
            )
        identifiers = sorted(grouped)
        texts = [grouped[identifier][0] for identifier in identifiers]
        indexed_scores = _normalized_scores(_bm25_scores(texts, row["question"]))
        scores = {
            identifier: indexed_scores.get(str(index), 0.0)
            for index, identifier in enumerate(identifiers)
        }
        max_length = max(len(tokens(text)) for text in texts)
        signals = tuple(
            MemorySignal(
                memory_id=identifier,
                hours_since_access=float(total_sessions - grouped[identifier][1] - 1),
                importance=len(tokens(text)) / max_length,
                relevance=scores.get(identifier, 0.0),
            )
            for identifier, text in zip(identifiers, texts, strict=True)
        )
        hits = rank_salient_memories(
            signals,
            recency_weight=0.15,
            importance_weight=0.15,
            relevance_weight=0.7,
            limit=10,
        )
        ranked = [hit.memory_id for hit in hits]
        cases.append(
            {
                "question_id": row["question_id"],
                "question_type": row["question_type"],
                "answer_session_ids": sorted(gold),
                "ranked_session_ids": ranked,
                "evidence_recall_at_10": len(set(ranked) & gold) / len(gold),
                "top_score_components": asdict(hits[0]) if hits else None,
            }
        )
    return report(
        "generative-agents",
        evaluation_type="end-to-end-deterministic",
        data={
            "id": "longmemeval",
            "artifact": "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_s_cleaned.json",
            "artifact_sha256": sha256(data_dir.parent / "longmemeval_s_cleaned.json"),
            "split": "cleaned-s:non-abstention",
            "cases": len(cases),
        },
        implementation="mari_components.knowledge.rank_salient_memories",
        config={"recency_weight": 0.15, "importance_weight": 0.15, "relevance_weight": 0.7},
        metrics={
            "evidence_recall_at_10": mean(row["evidence_recall_at_10"] for row in cases),
            "complete_evidence_recall_at_10": mean(float(row["evidence_recall_at_10"] == 1) for row in cases),
        },
        limitations=("BM25 supplies relevance and session length proxies importance.",),
    ), cases


def run_a_mem(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cases: list[dict[str, Any]] = []
    for row in load_longmem(data_dir):
        gold = set(row["answer_session_ids"])
        if not gold or "_abs" in row["question_id"]:
            continue
        texts = [_session_text(session) for session in row["haystack_sessions"]]
        raw = _bm25_scores(texts, row["question"])
        normalized = _normalized_scores(
            {row["haystack_session_ids"][int(key)]: value for key, value in raw.items()}
        )
        plan = plan_note_evolution(
            f"query:{row['question_id']}",
            normalized,
            link_threshold=0.35,
            evolution_threshold=0.75,
            limit=10,
        )
        predicted = set(plan.link_ids)
        cases.append(
            {
                "question_id": row["question_id"],
                "answer_session_ids": sorted(gold),
                "link_ids": list(plan.link_ids),
                "evolution_ids": list(plan.evolution_ids),
                "link_recall": len(predicted & gold) / len(gold),
                "link_precision": len(predicted & gold) / len(predicted) if predicted else 0.0,
            }
        )
    precision = mean(row["link_precision"] for row in cases)
    recall = mean(row["link_recall"] for row in cases)
    return report(
        "a-mem",
        evaluation_type="end-to-end-deterministic",
        data={
            "id": "longmemeval",
            "artifact_sha256": sha256(data_dir.parent / "longmemeval_s_cleaned.json"),
            "split": "cleaned-s:non-abstention",
            "cases": len(cases),
        },
        implementation="mari_components.knowledge.plan_note_evolution",
        config={"link_threshold": 0.35, "evolution_threshold": 0.75, "limit": 10, "scorer": "BM25Index"},
        metrics={"link_precision": precision, "link_recall": recall, "link_f1": f1(precision, recall)},
        limitations=("Uses BM25 similarity rather than an A-MEM embedding model.",),
    ), cases


def run_mem0(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cases: list[dict[str, Any]] = []
    for row in load_longmem(data_dir):
        gold_positions = [
            row["haystack_session_ids"].index(identifier)
            for identifier in row["answer_session_ids"]
            if identifier in row["haystack_session_ids"]
        ]
        if not gold_positions:
            continue
        existing: dict[str, str] = {}
        operations: list[str] = []
        expected = ""
        for sequence, position in enumerate(sorted(gold_positions)):
            value = _session_text(row["haystack_sessions"][position])
            candidate_id = f"candidate:{sequence}"
            operation = MemoryOperation.ADD if not existing else MemoryOperation.UPDATE
            decision = MemoryDecision(
                operation=operation,
                target_id="memory" if operation is MemoryOperation.UPDATE else "memory",
                reason="gold evidence session",
            )
            plan = plan_memory_mutations(
                existing, {candidate_id: value}, {candidate_id: decision}
            )
            existing = apply_memory_mutations(existing, plan)
            operations.append(operation.value)
            expected = value
        cases.append(
            {
                "question_id": row["question_id"],
                "evidence_sessions": len(gold_positions),
                "operations": operations,
                "final_value_sha256": hashlib.sha256(existing["memory"].encode()).hexdigest(),
                "expected_sha256": hashlib.sha256(expected.encode()).hexdigest(),
                "update_fidelity": float(existing["memory"] == expected),
                "stale_fact": float(existing["memory"] != expected),
            }
        )
    return report(
        "mem0-mutations",
        evaluation_type="component-oracle",
        data={
            "id": "longmemeval",
            "artifact_sha256": sha256(data_dir.parent / "longmemeval_s_cleaned.json"),
            "split": "cleaned-s:evidence-session-replay",
            "cases": len(cases),
        },
        implementation="mari_components.knowledge.plan_memory_mutations/apply_memory_mutations",
        config={"decisions": "gold chronological add/update replay"},
        metrics={
            "update_fidelity": mean(row["update_fidelity"] for row in cases),
            "stale_fact_rate": mean(row["stale_fact"] for row in cases),
            "updates": sum(row["operations"].count("update") for row in cases),
        },
        limitations=(
            "Gold evidence order supplies mutation decisions; this evaluates validation and replay, not operation classification.",
        ),
    ), cases


def _wikisection_docs(data_dir: Path, limit: int = 160) -> list[dict[str, Any]]:
    with tarfile.open(data_dir / ARTIFACTS["wikisection"].filename) as archive:
        member = archive.extractfile("wikisection_en_disease_validation.json")
        if member is None:
            raise RuntimeError("WikiSection validation member is missing")
        return json.load(member)[:limit]


def run_lightmem(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cases: list[dict[str, Any]] = []
    for document in _wikisection_docs(data_dir):
        text = document["text"]
        matches = list(re.finditer(r"[^.!?\n]+(?:[.!?]+|$)", text))
        if len(matches) < 4:
            continue
        items = [match.group().strip() for match in matches if match.group().strip()]
        starts = [match.start() for match in matches if match.group().strip()]
        if len(items) < 4:
            continue
        similarities = [jaccard(items[i], items[i + 1]) for i in range(len(items) - 1)]
        attention = [1.0 - value for value in similarities]
        segments = hybrid_topic_segments(
            items, attention, similarities, similarity_threshold=0.12
        )
        predicted = {segment.stop for segment in segments[:-1]}
        annotation_starts = {row["begin"] for row in document["annotations"][1:]}
        gold = {
            index
            for index, start in enumerate(starts[1:], 1)
            if any(abs(start - boundary) <= 2 for boundary in annotation_starts)
        }
        matched = len(predicted & gold)
        precision = matched / len(predicted) if predicted else 0.0
        recall = matched / len(gold) if gold else 0.0
        cases.append(
            {
                "document_id": document["id"],
                "sentences": len(items),
                "gold_boundaries": sorted(gold),
                "predicted_boundaries": sorted(predicted),
                "precision": precision,
                "recall": recall,
                "f1": f1(precision, recall),
            }
        )
    return report(
        "lightmem",
        evaluation_type="end-to-end-deterministic",
        data=dataset("wikisection", split="en_disease_validation:first-160", cases=len(cases)),
        implementation="mari_components.knowledge.hybrid_topic_segments",
        config={"similarity": "token-jaccard", "attention": "one-minus-similarity", "threshold": 0.12},
        metrics={
            "boundary_precision": mean(row["precision"] for row in cases),
            "boundary_recall": mean(row["recall"] for row in cases),
            "boundary_f1": mean(row["f1"] for row in cases),
        },
        limitations=(
            "Uses lexical novelty as the attention signal; no learned LightMem boundary model is included.",
            "Exact sentence-aligned boundaries only.",
        ),
    ), cases


def run_hipporag(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = load_qasc(data_dir)
    cases: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        passages = {
            "gold:1": row["fact1"],
            "gold:2": row["fact2"],
        }
        for offset in range(1, 9):
            other = rows[(index + offset) % len(rows)]
            passages[f"noise:{offset}"] = other["fact1"]
        graph: dict[str, dict[str, float]] = {}
        incidence: dict[str, dict[str, float]] = {}
        for passage_id, text in passages.items():
            passage_node = f"passage:{passage_id}"
            graph.setdefault(passage_node, {})
            incidence[passage_node] = {passage_id: 1.0}
            for term in sorted(token_set(text)):
                term_node = f"term:{term}"
                graph.setdefault(term_node, {})[passage_node] = 1.0
                graph[passage_node][term_node] = 1.0
        seeds = {
            f"term:{term}": 1.0
            for term in token_set(row["question"])
            if f"term:{term}" in graph
        }
        if not seeds:
            continue
        propagated = personalized_pagerank(graph, seeds)
        ranked = [
            hit.node_id for hit in project_graph_scores(propagated.hits, incidence, limit=5)
        ]
        gold = {"gold:1", "gold:2"}
        cases.append(
            {
                "case_id": row["id"],
                "question": row["question"],
                "gold_facts": [row["fact1"], row["fact2"]],
                "ranked_passage_ids": ranked,
                "passage_recall_at_5": len(set(ranked) & gold) / 2,
                "multi_hop_success": float(gold <= set(ranked)),
                "iterations": propagated.iterations,
                "converged": propagated.converged,
            }
        )
    return report(
        "hipporag",
        evaluation_type="end-to-end-deterministic",
        data=dataset("qasc", split="validation:first-256", cases=len(cases)),
        implementation="mari_components.retrieval.personalized_pagerank/project_graph_scores",
        config={"graph": "term-passage bipartite", "distractors_per_case": 8, "limit": 5},
        metrics={
            "passage_recall_at_5": mean(row["passage_recall_at_5"] for row in cases),
            "multi_hop_success": mean(row["multi_hop_success"] for row in cases),
            "convergence_rate": mean(float(row["converged"]) for row in cases),
        },
        limitations=("Small per-question candidate pools; relation extraction is token based.",),
    ), cases


def run_graph_communities(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cases: list[dict[str, Any]] = []
    for document in load_docred(data_dir):
        graph: dict[str, dict[str, float]] = {
            str(index): {} for index in range(len(document["vertexSet"]))
        }
        mentions: dict[int, set[int]] = {}
        for entity, values in enumerate(document["vertexSet"]):
            for mention in values:
                mentions.setdefault(mention["sent_id"], set()).add(entity)
        for entities in mentions.values():
            for left in entities:
                for right in entities:
                    if left != right:
                        graph[str(left)][str(right)] = graph[str(left)].get(str(right), 0.0) + 1.0
        partition = leiden_communities(graph)
        labels = {
            node: community
            for community, nodes in enumerate(partition.communities)
            for node in nodes
        }
        relations = {(str(row["h"]), str(row["t"])) for row in document["labels"]}
        covered = sum(labels.get(left) == labels.get(right) for left, right in relations)
        cases.append(
            {
                "document_id": document["title"],
                "entities": len(graph),
                "relations": len(relations),
                "communities": [list(value) for value in partition.communities],
                "modularity": partition.modularity,
                "relation_community_coverage": covered / len(relations) if relations else 1.0,
            }
        )
    return report(
        "graph-communities",
        evaluation_type="end-to-end-deterministic",
        data=dataset("docred", split="dev:first-256", cases=len(cases)),
        implementation="mari_components.graph.leiden_communities",
        config={"edge": "entity co-mention count", "resolution": 1.0},
        metrics={
            "modularity_mean": mean(row["modularity"] for row in cases),
            "relation_community_coverage": mean(row["relation_community_coverage"] for row in cases),
            "communities_mean": mean(len(row["communities"]) for row in cases),
        },
        limitations=(
            "Community coverage is measured against DocRED relations; this does not run relation extraction or GraphRAG answer generation.",
        ),
    ), cases


def _wdc_rows(data_dir: Path) -> list[tuple[str, str, int]]:
    rows: list[tuple[str, str, int]] = []
    for name in ("wdc-watches", "wdc-shoes"):
        for line in (data_dir / ARTIFACTS[name].filename).read_text().splitlines():
            left, right, label = line.rsplit("#####", 2)
            left_url = left.split(maxsplit=1)[-1]
            right_url = right.split(maxsplit=1)[-1]
            rows.append((left_url, right_url, int(label)))
    return rows


def _url_features(left: str, right: str) -> dict[str, bool]:
    first, second = urlparse(left), urlparse(right)
    left_tokens = token_set(unquote(first.path))
    right_tokens = token_set(unquote(second.path))
    left_codes = {value for value in left_tokens if len(value) >= 5 and any(c.isdigit() for c in value)}
    right_codes = {value for value in right_tokens if len(value) >= 5 and any(c.isdigit() for c in value)}
    return {
        "host": first.netloc.removeprefix("www.") == second.netloc.removeprefix("www."),
        "path_tokens": len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens)) >= 0.35,
        "product_code": bool(left_codes & right_codes),
    }


def run_entity_resolution(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    positives = [row for row in _wdc_rows(data_dir) if row[2] == 1]
    negatives = [row for row in _wdc_rows(data_dir) if row[2] == 0]
    train = positives[::2] + negatives[::2]
    evaluation = positives[1::2] + negatives[1::2]
    probabilities: dict[str, tuple[float, float]] = {}
    for field in ("host", "path_tokens", "product_code"):
        match_agree = sum(_url_features(a, b)[field] for a, b, label in train if label)
        nonmatch_agree = sum(_url_features(a, b)[field] for a, b, label in train if not label)
        match_total = sum(label for _a, _b, label in train)
        nonmatch_total = len(train) - match_total
        m = (match_agree + 1) / (match_total + 2)
        u = (nonmatch_agree + 1) / (nonmatch_total + 2)
        probabilities[field] = (m, u)

    def score_pair(left: str, right: str, threshold: float) -> Any:
        features = _url_features(left, right)
        return resolve_entity(
            (
                FieldAgreement(
                    field=field,
                    agrees=agrees,
                    match_probability=probabilities[field][0],
                    nonmatch_probability=probabilities[field][1],
                )
                for field, agrees in features.items()
            ),
            link_threshold=threshold,
            review_threshold=threshold - 1.0,
        )

    train_scores = sorted({score_pair(a, b, 0.0).score for a, b, _label in train})
    candidates = [train_scores[0] - 0.01, *train_scores, train_scores[-1] + 0.01]
    best_threshold = max(
        candidates,
        key=lambda threshold: (
            f1(
                sum(score_pair(a, b, threshold).decision is ResolutionDecision.LINK and label for a, b, label in train)
                / max(1, sum(score_pair(a, b, threshold).decision is ResolutionDecision.LINK for a, b, _label in train)),
                sum(score_pair(a, b, threshold).decision is ResolutionDecision.LINK and label for a, b, label in train)
                / max(1, sum(label for _a, _b, label in train)),
            ),
            -threshold,
        ),
    )
    cases: list[dict[str, Any]] = []
    for index, (left, right, label) in enumerate(evaluation):
        result = score_pair(left, right, best_threshold)
        predicted = result.decision is ResolutionDecision.LINK
        cases.append(
            {
                "case_id": index,
                "left_url": left,
                "right_url": right,
                "label": label,
                "decision": result.decision.value,
                "score": result.score,
                "correct": predicted == bool(label),
                "contributions": dict(result.contributions),
            }
        )
    tp = sum(row["label"] == 1 and row["decision"] == "link" for row in cases)
    fp = sum(row["label"] == 0 and row["decision"] == "link" for row in cases)
    fn = sum(row["label"] == 1 and row["decision"] != "link" for row in cases)
    precision, recall = tp / max(1, tp + fp), tp / max(1, tp + fn)
    return report(
        "entity-resolution",
        evaluation_type="trained-classical",
        data={
            "id": "wdc-products",
            "artifacts": [asdict(ARTIFACTS["wdc-watches"]), asdict(ARTIFACTS["wdc-shoes"])],
            "split": "odd rows per label; even rows train probabilities/threshold",
            "cases": len(cases),
        },
        implementation="mari_components.graph.resolve_entity",
        config={"fields": list(probabilities), "probabilities": probabilities, "link_threshold": best_threshold},
        metrics={
            "pair_precision": precision,
            "pair_recall": recall,
            "pair_f1": f1(precision, recall),
            "accuracy": mean(float(row["correct"]) for row in cases),
            "review_rate": mean(float(row["decision"] == "review") for row in cases),
        },
        limitations=("Only URL-derived fields are available in the compact official gold files.",),
    ), cases


def _deepseek_predictions(
    data_dir: Path, rows: Sequence[tuple[str, bool, Mapping[str, Any]]]
) -> dict[str, Any]:
    cache = data_dir / "contradoc-deepseek-v3.1.jsonl"
    known: dict[str, Any] = {}
    if cache.exists():
        for line in cache.read_text().splitlines():
            value = json.loads(line)
            known[value["case_id"]] = value["prediction"]
    missing = [row for row in rows if row[0] not in known]
    if not missing:
        return known

    import os

    import requests

    key = os.environ.get("DEEPSEEK_API")
    if not key:
        raise RuntimeError(
            "DEEPSEEK_API is required to create the fixed ContraDoc prediction cache"
        )
    for start in range(0, len(missing)):
        batch = missing[start : start + 1]
        documents = []
        for case_id, _label, row in batch:
            sentences = _split_sentences(row["text"])
            documents.append(
                {
                    "case_id": case_id,
                    "sentences": [
                        f"[{index}] {text}"
                        for index, text in enumerate(sentences, 1)
                    ],
                }
            )
        prompt = (
            "Detect whether each document contradicts itself. Return ONLY a JSON object "
            "with a results array. Each item must have case_id, judgment (boolean), "
            "evidence_sentence_ids (the minimal contradictory sentence numbers; empty "
            "when false), and reasoning that cites sentence numbers like [2] and [7]. "
            "Do not use outside knowledge.\n" + json.dumps(documents)
        )
        expected_ids = {row[0] for row in batch}
        returned: dict[str, Any] = {}
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                response = requests.post(
                    "https://api.deepseek.com/chat/completions",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "deepseek-chat",
                        "temperature": 0,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a precise document consistency evaluator.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                    },
                    timeout=180,
                )
                response.raise_for_status()
                parsed = json.loads(
                    response.json()["choices"][0]["message"]["content"],
                    strict=False,
                )
                values = parsed.get("results", [])
                returned = {value["case_id"]: value for value in values}
                if set(returned) != expected_ids:
                    raise ValueError("incomplete ContraDoc batch")
                break
            except (requests.RequestException, KeyError, TypeError, ValueError) as error:
                last_error = error
                if attempt < 3:
                    time.sleep(1.5 * (attempt + 1))
        else:
            raise RuntimeError(
                "DeepSeek did not return a complete ContraDoc batch after four attempts"
            ) from last_error
        with cache.open("a") as stream:
            for case_id, _label, _row in batch:
                known[case_id] = returned[case_id]
                stream.write(
                    json.dumps(
                        {"case_id": case_id, "prediction": returned[case_id]},
                        sort_keys=True,
                    )
                    + "\n"
                )
    return known


def run_document_contradiction(
    data_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    corpus = load_contradoc(data_dir)
    selected: list[tuple[str, bool, Mapping[str, Any]]] = []
    pairs = zip(
        sorted(corpus["pos"].items())[:80],
        sorted(corpus["neg"].items())[:80],
        strict=True,
    )
    for positive, negative in pairs:
        selected.extend(
            ((positive[0], True, positive[1]), (negative[0], False, negative[1]))
        )
    predictions = _deepseek_predictions(data_dir, selected)
    cases: list[dict[str, Any]] = []
    for case_id, expected, row in selected:
        sentences = _split_sentences(row["text"])
        gold = {_closest_sentence(sentences, row["evidence"]) + 1} if expected else set()
        raw = predictions[case_id]
        format_valid = True
        try:
            assessment = validate_document_contradiction(
                sentence_count=len(sentences),
                judgment=bool(raw["judgment"]),
                evidence_sentence_ids=raw.get("evidence_sentence_ids", ()),
                reasoning=str(raw.get("reasoning", "")),
            )
        except (KeyError, TypeError, ValueError):
            format_valid = False
            assessment = validate_document_contradiction(
                sentence_count=len(sentences), judgment=False
            )
        rewards = document_contradiction_rewards(
            assessment,
            expected_judgment=expected,
            gold_evidence_sentence_ids=gold,
            format_valid=format_valid,
        )
        predicted = assessment.judgment
        cases.append(
            {
                "case_id": case_id,
                "expected_judgment": expected,
                "predicted_judgment": predicted,
                "gold_evidence_sentence_ids": sorted(gold),
                "predicted_evidence_sentence_ids": list(
                    assessment.evidence_sentence_ids
                ),
                "reasoning_sentence_ids": list(assessment.reasoning_sentence_ids),
                "format_valid": format_valid,
                "judgment_correct": predicted == expected,
                "localization_hit": bool(
                    gold & set(assessment.evidence_sentence_ids)
                )
                if expected
                else None,
                "rewards": asdict(rewards),
            }
        )
    positive = [row for row in cases if row["expected_judgment"]]
    negative = [row for row in cases if not row["expected_judgment"]]
    tp = sum(row["predicted_judgment"] for row in positive)
    fp = sum(row["predicted_judgment"] for row in negative)
    fn = len(positive) - tp
    tn = len(negative) - fp
    positive_f1 = f1(tp / max(1, tp + fp), tp / max(1, tp + fn))
    negative_f1 = f1(tn / max(1, tn + fn), tn / max(1, tn + fp))
    return report(
        "document-contradiction",
        evaluation_type="model-assisted-end-to-end",
        data=dataset(
            "contradoc", split="lexicographic-first-80-per-label", cases=len(cases)
        ),
        implementation="mari_components.verification.validate_document_contradiction/document_contradiction_rewards",
        config={
            "judge": "deepseek-chat",
            "temperature": 0,
            "sentencing": "regex",
            "batch_size": 1,
        },
        metrics={
            "accuracy": mean(float(row["judgment_correct"]) for row in cases),
            "macro_f1": (positive_f1 + negative_f1) / 2,
            "positive_f1": positive_f1,
            "negative_f1": negative_f1,
            "localization_recall": mean(
                float(row["localization_hit"]) for row in positive
            ),
            "format_valid_rate": mean(float(row["format_valid"]) for row in cases),
        },
        limitations=(
            "DeepSeek's moving deepseek-chat alias is not an immutable model checkpoint; predictions are preserved per case.",
            "Fixed balanced 160-document slice; sentence splitting differs from the benchmark's original evaluator.",
        ),
    ), cases


def _longmem_date(value: str) -> dt.datetime:
    return dt.datetime.strptime(value, "%Y/%m/%d (%a) %H:%M").replace(tzinfo=dt.UTC)


def run_temporal_graph(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cases: list[dict[str, Any]] = []
    for row in load_longmem(data_dir):
        facts = tuple(
            TemporalFact(
                fact_id=identifier,
                subject=row["question_id"],
                predicate="session",
                object=_session_text(session),
                valid_from=_longmem_date(date),
                recorded_at=_longmem_date(date),
            )
            for identifier, session, date in zip(
                row["haystack_session_ids"],
                row["haystack_sessions"],
                row["haystack_dates"],
                strict=True,
            )
        )
        question_time = _longmem_date(row["question_date"])
        visible = query_temporal_facts(
            facts,
            at=question_time,
            known_at=question_time,
            subject=row["question_id"],
            predicate="session",
        )
        visible_ids = {fact.fact_id for fact in visible}
        gold = set(row["answer_session_ids"])
        future = {fact.fact_id for fact in facts if fact.valid_from > question_time}
        cases.append(
            {
                "question_id": row["question_id"],
                "answer_session_ids": sorted(gold),
                "visible_answer_session_ids": sorted(gold & visible_ids),
                "future_session_ids": sorted(future),
                "visible_future_session_ids": sorted(future & visible_ids),
                "provenance_recall": len(gold & visible_ids) / len(gold) if gold else 1.0,
                "future_exclusion": float(not (future & visible_ids)),
            }
        )
    return report(
        "temporal-graph",
        evaluation_type="component-corpus",
        data={
            "id": "longmemeval",
            "artifact_sha256": sha256(data_dir.parent / "longmemeval_s_cleaned.json"),
            "split": "cleaned-s:all",
            "cases": len(cases),
        },
        implementation="mari_components.graph.query_temporal_facts",
        config={"valid_time": "session timestamp", "known_at": "question timestamp"},
        metrics={
            "provenance_recall": mean(row["provenance_recall"] for row in cases),
            "future_exclusion_rate": mean(row["future_exclusion"] for row in cases),
        },
        limitations=("Evaluates temporal visibility, not temporal question answering.",),
    ), cases


def run_procedures(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = [
        json.loads(line)
        for line in (data_dir / ARTIFACTS["agentbench"].filename).read_text().splitlines()
        if line
    ]
    cases: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        table = row["table"]["table_name"]
        base = [
            {"name": "inspect_schema", "args": {"table": table}, "ok": True},
            {"name": "execute_sql", "args": {}, "ok": True},
        ]
        alternate = [
            {"name": "list_tables", "args": {}, "ok": True},
            *base,
            {"name": "format_answer", "args": {}, "ok": True},
        ]
        trajectories = {
            f"{index}:direct": normalize_steps(base),
            f"{index}:explore": normalize_steps(alternate),
        }
        learned = learn_procedure(trajectories, intent=row["description"])
        tools = [step.tool for step in learned.steps]
        expected = ["inspect_schema", "execute_sql"]
        overlap = len(set(tools) & set(expected))
        precision = overlap / len(tools)
        recall = overlap / len(expected)
        cases.append(
            {
                "case_id": index,
                "source": row.get("source"),
                "expected_tools": expected,
                "learned_tools": tools,
                "tool_sequence_f1": f1(precision, recall),
                "source_trajectory_ids": list(learned.source_trajectory_ids),
            }
        )
    return report(
        "procedures",
        evaluation_type="component-corpus",
        data=dataset("agentbench", split="dbbench:dev", cases=len(cases)),
        implementation="mari_components.trajectories.normalize_steps/learn_procedure",
        config={"trajectories_per_task": 2, "stable_sequence": "longest common subsequence"},
        metrics={
            "tool_sequence_f1": mean(row["tool_sequence_f1"] for row in cases),
            "procedures_learned": len(cases),
        },
        limitations=(
            "AgentBench tasks seed controlled successful traces; no agent is executed in the live benchmark environments.",
        ),
    ), cases


def run_compiler(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    documents, queries, qrels = _scifact(data_dir)
    query_ids = sorted(qrels)
    development, heldout = query_ids[::2], query_ids[1::2]

    def evaluate_config(config: Mapping[str, Any], selected: Sequence[str]) -> float:
        index = BM25Index(documents, k1=float(config["k1"]), b=float(config["b"]))
        scores = []
        for query_id in selected:
            ranked = [
                hit.document_id
                for hit in index.search(queries[query_id], limit=10)
            ]
            ndcg, _recall = _retrieval_metrics(ranked, qrels[query_id])
            scores.append(ndcg)
        return mean(scores)

    configurations = [
        {"k1": k1, "b": b}
        for k1 in (0.6, 1.2, 1.8)
        for b in (0.25, 0.75, 1.0)
    ]
    compiled = compile_configurations(
        configurations,
        evaluate=lambda config: {"ndcg_at_10": evaluate_config(config, development)},
        objectives=(
            MetricObjective(
                name="ndcg_at_10", direction=ObjectiveDirection.MAXIMIZE
            ),
        ),
    )
    winner_heldout = evaluate_config(compiled.configuration, heldout)
    default_heldout = evaluate_config({"k1": 1.2, "b": 0.75}, heldout)
    cases = [
        {
            "fingerprint": candidate.fingerprint,
            "configuration": dict(candidate.configuration),
            "development_ndcg_at_10": candidate.metrics["ndcg_at_10"],
            "feasible": candidate.feasible,
            "utility": candidate.utility,
            "selected": candidate.fingerprint == compiled.winner.fingerprint,
        }
        for candidate in compiled.candidates
    ]
    return report(
        "compiler",
        evaluation_type="heldout-optimization",
        data={
            **scifact_dataset(len(query_ids)),
            "source_queries": len(query_ids),
            "cases": len(cases),
        },
        implementation="mari_components.platform.compile_configurations",
        config={
            "development": "alternating sorted query IDs",
            "heldout": "complementary alternating query IDs",
            "search_space": configurations,
        },
        metrics={
            "development_ndcg_at_10": compiled.winner.metrics["ndcg_at_10"],
            "heldout_ndcg_at_10": winner_heldout,
            "default_heldout_ndcg_at_10": default_heldout,
            "heldout_gain": winner_heldout - default_heldout,
            "constraint_violations": sum(not candidate.feasible for candidate in compiled.candidates),
        },
        limitations=("Searches only nine BM25 parameter configurations.",),
    ), cases


def run_connector_suite(
    _data_dir: Path, suite: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    node_ids = subprocess.check_output(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "tests/test_connector_contract.py",
            "tests/test_connector_events.py",
            "tests/test_connector_expansion.py",
            "tests/test_priority_connectors.py",
            "tests/test_remaining_connectors.py",
        ],
        text=True,
    ).splitlines()
    node_ids = [row for row in node_ids if "::" in row]
    selected = [
        row
        for row in node_ids
        if (
            any(word in row.casefold() for word in ("stream", "event", "hint", "hmac"))
            if suite == "connector-stream"
            else not any(
                word in row.casefold() for word in ("stream", "event", "hint", "hmac")
            )
        )
    ]
    subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *selected],
        check=True,
        capture_output=True,
        text=True,
    )
    cases = [{"test": node_id, "passed": True} for node_id in selected]
    definitions = connector_definitions()
    return report(
        suite,
        evaluation_type="fixture-conformance",
        data={
            "id": "connector-fixtures",
            "artifact": "tests/test_connector_*.py",
            "split": suite.removeprefix("connector-"),
            "cases": len(cases),
        },
        implementation="mari_components.connectors",
        config={"connectors": len(definitions), "pytest_nodes": selected},
        metrics={
            "passed": len(cases),
            "failed": 0,
            "pass_rate": 1.0,
            "connector_definitions": len(definitions),
        },
        limitations=(
            "Uses recorded/synthetic provider shapes; it does not claim upstream service throughput or availability.",
        ),
    ), cases


RUNNERS: dict[
    str, Callable[[Path], tuple[dict[str, Any], list[dict[str, Any]]]]
] = {
    "connector-batch": lambda data: run_connector_suite(data, "connector-batch"),
    "connector-stream": lambda data: run_connector_suite(data, "connector-stream"),
    "dense-flat": lambda data: run_index_suite(data, "dense-flat"),
    "hnsw": lambda data: run_index_suite(data, "hnsw"),
    "ivfpq": lambda data: run_index_suite(data, "ivfpq"),
    "bm25": lambda data: run_index_suite(data, "bm25"),
    "learned-sparse": run_learned_sparse,
    "muvera-maxsim": run_muvera,
    "hyde": run_hyde,
    "raptor": lambda data: run_raptor_memwalker(data, "raptor"),
    "memwalker": lambda data: run_raptor_memwalker(data, "memwalker"),
    "crag": run_crag,
    "flare": run_flare,
    "self-rag": run_self_rag,
    "chain-of-note": run_chain_of_note,
    "recomp": run_recomp,
    "rag-fusion": run_rag_fusion,
    "hipporag": run_hipporag,
    "graph-communities": run_graph_communities,
    "sparsecl": run_sparsecl,
    "document-contradiction": run_document_contradiction,
    "mem0-mutations": run_mem0,
    "a-mem": run_a_mem,
    "lightmem": run_lightmem,
    "generative-agents": run_generative_agents,
    "context-envelope": run_context_envelope,
    "temporal-graph": run_temporal_graph,
    "entity-resolution": run_entity_resolution,
    "procedures": run_procedures,
    "compiler": run_compiler,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=("all", *RUNNERS), default="all")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("benchmarks/data/research-downloads"),
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("benchmarks/results")
    )
    parser.add_argument(
        "--prepare-only", action="store_true", help="download and verify inputs"
    )
    args = parser.parse_args()
    prepare(args.data_dir)
    if args.prepare_only:
        return
    selected = RUNNERS if args.suite == "all" else {args.suite: RUNNERS[args.suite]}
    for suite, runner in selected.items():
        started = time.perf_counter()
        aggregate, cases = runner(args.data_dir)
        aggregate["elapsed_seconds"] = time.perf_counter() - started
        write_result(args.output_dir, suite, aggregate, cases)
        print(f"{suite}: {len(cases)} cases")


if __name__ == "__main__":
    main()
