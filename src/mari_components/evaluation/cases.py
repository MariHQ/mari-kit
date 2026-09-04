"""Normalized cases and adapters for public knowledge-system corpora."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

from mari_components.json import freeze_json_mapping


@dataclass(frozen=True, slots=True, kw_only=True)
class RetrievalCase:
    case_id: str
    query: str
    relevance: Mapping[str, float]

    def __post_init__(self) -> None:
        if not self.case_id or not self.query or not self.relevance:
            raise ValueError("retrieval cases require ID, query, and relevance")
        object.__setattr__(self, "relevance", MappingProxyType(dict(self.relevance)))


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceCase:
    case_id: str
    claim: str
    label: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class MemoryCase:
    case_id: str
    question: str
    expected_answer: str
    capability: str
    sessions: tuple[Any, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (
            not self.case_id
            or not self.question
            or not self.expected_answer
            or not self.capability
        ):
            raise ValueError(
                "memory cases require ID, question, answer, and capability"
            )
        object.__setattr__(self, "sessions", tuple(self.sessions))
        object.__setattr__(self, "metadata", freeze_json_mapping(self.metadata))


def _jsonl(path: str | Path) -> Iterator[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"line {line_number} must contain an object")
            yield value


def load_beir_cases(
    queries_path: str | Path, qrels_path: str | Path
) -> tuple[RetrievalCase, ...]:
    """Load BEIR query JSONL and headered TSV qrels without BEIR dependencies."""

    queries = {str(row["_id"]): str(row["text"]) for row in _jsonl(queries_path)}
    relevance: dict[str, dict[str, float]] = {}
    with Path(qrels_path).open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            query_id = str(row.get("query-id") or row.get("query_id") or "")
            corpus_id = str(row.get("corpus-id") or row.get("corpus_id") or "")
            score = float(row.get("score") or 0)
            if query_id and corpus_id and score > 0:
                relevance.setdefault(query_id, {})[corpus_id] = score
    missing = set(relevance) - set(queries)
    if missing:
        raise ValueError(f"qrels reference missing queries: {sorted(missing)[:5]!r}")
    return tuple(
        RetrievalCase(
            case_id=query_id, query=queries[query_id], relevance=relevance[query_id]
        )
        for query_id in sorted(relevance)
    )


def load_fever_cases(path: str | Path) -> tuple[EvidenceCase, ...]:
    """Normalize FEVER claims and all annotated Wikipedia line IDs."""

    output: list[EvidenceCase] = []
    for row in _jsonl(path):
        evidence_ids: set[str] = set()
        for evidence_set in row.get("evidence") or []:
            if not isinstance(evidence_set, list):
                continue
            for annotation in evidence_set:
                if (
                    isinstance(annotation, list)
                    and len(annotation) >= 4
                    and annotation[2] is not None
                ):
                    evidence_ids.add(f"{annotation[2]}#{annotation[3]}")
        output.append(
            EvidenceCase(
                case_id=str(row["id"]),
                claim=str(row["claim"]),
                label=str(row["label"]),
                evidence_ids=tuple(sorted(evidence_ids)),
            )
        )
    return tuple(output)


def load_longmemeval_cases(path: str | Path) -> tuple[MemoryCase, ...]:
    """Load the official cleaned LongMemEval array while dropping gold side channels."""

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("LongMemEval data must be a JSON array")
    output: list[MemoryCase] = []
    for row in raw:
        if not isinstance(row, dict):
            raise ValueError("LongMemEval rows must be objects")
        sessions = row.get("haystack_sessions") or row.get("history") or []
        metadata = {
            key: value
            for key, value in row.items()
            if key not in {"question", "answer", "haystack_sessions", "history"}
            and not key.startswith("answer_")
        }
        output.append(
            MemoryCase(
                case_id=str(row.get("question_id") or row.get("id") or len(output)),
                question=str(row["question"]),
                expected_answer=str(row["answer"]),
                capability=str(
                    row.get("question_type") or row.get("category") or "unknown"
                ),
                sessions=tuple(sessions),
                metadata=metadata,
            )
        )
    return tuple(output)


def group_memory_cases(
    cases: Iterable[MemoryCase],
) -> Mapping[str, tuple[MemoryCase, ...]]:
    grouped: dict[str, list[MemoryCase]] = {}
    for case in cases:
        grouped.setdefault(case.capability, []).append(case)
    return MappingProxyType(
        {key: tuple(values) for key, values in sorted(grouped.items())}
    )
