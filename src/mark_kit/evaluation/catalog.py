"""Read and validate Mari benchmark corpus catalogs."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True, slots=True, kw_only=True)
class Corpus:
    """One versioned external corpus and its evaluation contract."""

    corpus_id: str
    name: str
    tasks: tuple[str, ...]
    metrics: tuple[str, ...]
    homepage: str
    license: str
    access: str
    notes: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class CorpusCatalog:
    """Immutable, addressable collection of corpus declarations."""

    schema_version: int
    corpora: tuple[Corpus, ...]
    _by_id: Mapping[str, Corpus]

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError(f"unsupported catalog schema: {self.schema_version}")
        ids = [corpus.corpus_id for corpus in self.corpora]
        if len(ids) != len(set(ids)):
            raise ValueError("corpus ids must be unique")
        object.__setattr__(self, "_by_id", MappingProxyType(dict(self._by_id)))

    def __getitem__(self, corpus_id: str) -> Corpus:
        return self._by_id[corpus_id]

    def for_task(self, task: str) -> tuple[Corpus, ...]:
        """Return all corpora declaring an exact task tag."""

        return tuple(corpus for corpus in self.corpora if task in corpus.tasks)


def _strings(value: Any, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be a list of strings")
    return tuple(value)


def _corpus(value: Any) -> Corpus:
    if not isinstance(value, dict):
        raise ValueError("each corpus must be an object")
    required = ("id", "name", "tasks", "metrics", "homepage", "license", "access")
    missing = [field for field in required if field not in value]
    if missing:
        raise ValueError(f"corpus is missing fields: {', '.join(missing)}")
    scalar = ("id", "name", "homepage", "license", "access")
    if any(not isinstance(value[field], str) or not value[field] for field in scalar):
        raise ValueError("corpus scalar fields must be non-empty strings")
    notes = value.get("notes", "")
    if not isinstance(notes, str):
        raise ValueError("notes must be a string")
    return Corpus(
        corpus_id=value["id"],
        name=value["name"],
        tasks=_strings(value["tasks"], field="tasks"),
        metrics=_strings(value["metrics"], field="metrics"),
        homepage=value["homepage"],
        license=value["license"],
        access=value["access"],
        notes=notes,
    )


def load_catalog(path: str | Path) -> CorpusCatalog:
    """Load a catalog without downloading or accepting any dataset terms."""

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("schema_version"), int):
        raise ValueError("catalog must contain an integer schema_version")
    values = raw.get("corpora")
    if not isinstance(values, list):
        raise ValueError("catalog corpora must be a list")
    corpora = tuple(_corpus(value) for value in values)
    return CorpusCatalog(
        schema_version=raw["schema_version"],
        corpora=corpora,
        _by_id={corpus.corpus_id: corpus for corpus in corpora},
    )


def catalog_rows(corpora: Iterable[Corpus]) -> tuple[dict[str, object], ...]:
    """Produce serialization-friendly rows for reports and UIs."""

    return tuple(
        {
            "id": corpus.corpus_id,
            "name": corpus.name,
            "tasks": list(corpus.tasks),
            "metrics": list(corpus.metrics),
            "homepage": corpus.homepage,
            "license": corpus.license,
            "access": corpus.access,
            "notes": corpus.notes,
        }
        for corpus in corpora
    )
