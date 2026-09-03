# Mari benchmarks

Mari now has measured public-corpus baselines. The committed [result reports](results/README.md) cover the full BEIR SciFact test split, the full cleaned LongMemEval-S retrieval split, and an exact-versus-approximate index comparison over SciFact documents. Every run preserves the corpus revision, split, Mari commit, configuration, latency, environment, and per-case rankings.

`catalog.json` records candidate public corpora without downloading them or accepting their terms. A repository license does not necessarily cover embedded source documents. Review the declared dataset terms before caching or redistributing a corpus.

## Measured profiles

- BEIR SciFact: BM25 over 5,183 documents and all 300 test queries.
- LongMemEval-S: session BM25 over all 470 scored memory questions; the 30 abstention cases are skipped per the official evaluator.
- SciFact index comparison: dense flat, HNSW, and IVF-PQ over the same 512-document, 64-query deterministic slice.

The remaining entries in `catalog.json` are candidates, not completed benchmarks. They must not be described as results until a corpus-backed run and case records exist.

## Catalog access

```python
from mari_components.evaluation import load_catalog

catalog = load_catalog("benchmarks/catalog.json")
for corpus in catalog.for_task("evidence-retrieval"):
    print(corpus.name, corpus.metrics, corpus.license)
```

The paper-to-suite contract is queryable independently:

```python
from mari_components.evaluation import load_suite_catalog

suites = load_suite_catalog("benchmarks/suites.json")
for suite in suites.for_paper("2406.10746"):
    print(suite.suite_id, suite.corpora, suite.metrics)
```

## Retrieval run format

The deterministic runner consumes one JSON object per query. `relevance` may contain binary or graded judgments.

```json
{"query_id":"q1","ranked_ids":["d2","d1"],"relevance":{"d1":2,"d2":1}}
```

```shell
python benchmarks/evaluate_retrieval.py run.jsonl --k 10
```

## Reproduce

```shell
python benchmarks/run_public.py all
python benchmarks/verify_results.py
```

Public corpora are not committed here. The runner downloads checksum-pinned copies under `benchmarks/data/`; that path is ignored by Git. Aggregate JSON and every per-case ranking are committed under `benchmarks/results/`.
