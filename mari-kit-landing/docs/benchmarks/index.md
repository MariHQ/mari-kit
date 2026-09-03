# Benchmarks and evaluations

## Measured baselines

These numbers come from committed public-corpus runs. Each aggregate links to per-case rankings in the repository and can be recomputed locally.

### BEIR SciFact retrieval

5,183 documents, all 300 test queries, BM25 with `k1=1.2` and `b=0.75`.

| nDCG@10 | MRR@10 | Recall@10 | Recall@100 | p50 query | p95 query |
|---:|---:|---:|---:|---:|---:|
| 0.6634 | 0.6309 | 0.7876 | 0.8826 | 56.02 ms | 67.63 ms |

### LongMemEval-S session retrieval

The full cleaned small split contains 500 questions. The official evaluator excludes 30 `_abs` questions because no history evidence exists, leaving 470 scored cases. Mari indexes each timestamped conversation session as one BM25 document.

| Recall all@5 | Recall all@10 | nDCG any@5 | nDCG any@10 | p50 query | p95 query |
|---:|---:|---:|---:|---:|---:|
| 0.8298 | 0.9021 | 0.8835 | 0.8972 | 3.16 ms | 3.69 ms |

`Recall all@k` is one only when every annotated evidence session appears in the top `k`. The main remaining failures are multi-session, temporal, and implicit-preference questions; a high `Recall any` would conceal those failures.

### Exact and approximate indexes

This index-only run holds a deterministic 128-dimensional feature-hashing encoder constant across 512 SciFact documents and 64 queries. ANN Recall@10 compares each approximate result to exact dense search.

| Index | Build | ANN Recall@10 | Corpus Recall@10 | p50 query |
|---|---:|---:|---:|---:|
| Dense flat | 1.3 ms | 1.0000 | 0.3906 | 0.24 ms |
| HNSW | 240 ms | 0.4391 | 0.2214 | 0.21 ms |
| IVF-PQ | 46 ms | 0.2563 | 0.2318 | 1.11 ms |

The current HNSW and IVF-PQ settings lose too many exact neighbors. They are measured reference implementations, not recommended production defaults.

Mari evaluates stages before end-to-end answers. A weak final score can originate in parsing, retrieval, evidence selection, policy, context packing, or generation; one aggregate number cannot distinguish them.

## Run contract

```python
from mari_components.evaluation import (
    evaluate_retrieval,
    load_catalog,
    load_suite_catalog,
)

catalog = load_catalog("benchmarks/catalog.json")
suites = load_suite_catalog("benchmarks/suites.json")
case_score = evaluate_retrieval(
    ranked_ids=["passage-7", "passage-2", "passage-9"],
    relevance={"passage-2": 2.0, "passage-7": 1.0},
    k=10,
)
print(case_score.ndcg, case_score.recall)
```

Every persisted public run identifies the corpus artifact and checksum, split, Mari commit and implementation hash, exact configuration, runtime environment, build and query timings, and per-case outputs. Model-backed suites must additionally pin model and prompt identifiers and record token counts. Dataset artifacts remain outside Git.

## Evaluation path

:::{container} diagram benchmark-flow
frozen corpus *→* adapter *→* Mari stage *→* predictions + traces *→* deterministic metrics *→* regression gate
:::

## Planned corpus coverage

The table below is the evaluation backlog. A catalog entry is not a result.

| Capability | Primary corpus | Primary measurements |
|---|---|---|
| Retrieval and indexes | BEIR, LoTTE | nDCG@10, Recall@100, MRR, latency, index bytes |
| Parsing and sections | QASPER, WikiSection | text preservation, Boundary F1, Pk, WindowDiff |
| Evidence and verification | FEVER, FEVEROUS, QASPER | evidence F1, verdict accuracy, answer F1 |
| Contradictions | ContraDoc, BEIR ArguAna | macro-F1, localization F1, contradiction Recall@k |
| Graph construction | DocRED, QASC | relation F1, provenance recall, multi-hop accuracy |
| Entity resolution | WDC Products | pair/cluster F1, pairs completeness, reduction ratio |
| Freshness | FreshQA plus revision replay | strict accuracy, stale-answer rate, time-to-consistency |
| Memory | LongMemEval | accuracy by capability, evidence Recall@k, reader tokens |
| Context assembly | LongBench, QASPER | score by length and budget, evidence density |

## Licensing boundary

The catalog records access and license notes but does not download anything. Benchmark code and benchmark data can have different licenses, and aggregate suites such as BEIR and LongBench retain the terms of their constituent datasets. Review upstream terms before local caching, derived-data publication, or commercial use.

```{toctree}
:maxdepth: 1
:hidden:

running
suites
reference-validation
```
