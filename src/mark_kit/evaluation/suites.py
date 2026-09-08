"""Machine-readable mappings from papers and APIs to benchmark contracts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkSuite:
    suite_id: str
    api: str
    papers: tuple[str, ...]
    corpora: tuple[str, ...]
    metrics: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkSuiteCatalog:
    schema_version: int
    suites: tuple[BenchmarkSuite, ...]

    def get(self, suite_id: str) -> BenchmarkSuite:
        for suite in self.suites:
            if suite.suite_id == suite_id:
                return suite
        raise KeyError(suite_id)

    def for_paper(self, paper_id: str) -> tuple[BenchmarkSuite, ...]:
        return tuple(suite for suite in self.suites if paper_id in suite.papers)


def load_suite_catalog(path: str | Path) -> BenchmarkSuiteCatalog:
    """Load and validate a paper-to-evaluation contract manifest."""

    raw = json.loads(Path(path).read_text())
    suites = tuple(
        BenchmarkSuite(
            suite_id=str(row["id"]),
            api=str(row["api"]),
            papers=tuple(str(value) for value in row["papers"]),
            corpora=tuple(str(value) for value in row["corpora"]),
            metrics=tuple(str(value) for value in row["metrics"]),
        )
        for row in raw["suites"]
    )
    ids = [suite.suite_id for suite in suites]
    if len(ids) != len(set(ids)):
        raise ValueError("benchmark suite IDs must be unique")
    if any(
        not suite.suite_id.strip()
        or not suite.api.strip()
        or not suite.papers
        or not suite.corpora
        or not suite.metrics
        for suite in suites
    ):
        raise ValueError(
            "each benchmark suite requires an ID, API, papers, corpora, and metrics"
        )
    return BenchmarkSuiteCatalog(
        schema_version=int(raw["schema_version"]), suites=suites
    )
