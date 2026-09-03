# Measured benchmark runs

These are recorded outputs from `python benchmarks/run_public.py all`, not target values or fixture tests. The corpus files are excluded from Git; each report pins the public artifact checksum, code commit, runtime, configuration, aggregate measurements, and environment. The adjacent JSONL contains every ranked case.

## Results

### BEIR SciFact retrieval

Full public test split: 5,183 documents and 300 judged queries.

| Mari implementation | nDCG@10 | MRR@10 | Recall@10 | Recall@100 | Query p50 | Query p95 |
|---|---:|---:|---:|---:|---:|---:|
| BM25 (`k1=1.2`, `b=0.75`) | 0.6634 | 0.6309 | 0.7876 | 0.8826 | 56.02 ms | 67.63 ms |

### LongMemEval-S session retrieval

Full cleaned public small split: 500 questions, with the benchmark's 30 `_abs` cases excluded exactly as in the official evaluator. The 470 scored questions retrieve among roughly 50 timestamped sessions each. `Recall all` requires every evidence session to be present.

| Mari implementation | Recall all@5 | Recall all@10 | nDCG any@5 | nDCG any@10 | Query p50 | Query p95 |
|---|---:|---:|---:|---:|---:|---:|
| Session BM25 | 0.8298 | 0.9021 | 0.8835 | 0.8972 | 3.16 ms | 3.69 ms |

The weakest Recall all@10 categories are `multi-session` (0.8182), `temporal-reasoning` (0.8504), and `single-session-preference` (0.8667). The report retains all per-category measurements.

### SciFact-derived index comparison

Index-only run over 512 real SciFact documents and 64 judged queries. A fixed 128-dimensional signed feature hash holds the encoder constant. `ANN Recall@10` measures overlap with Mari's exact top ten; it does not claim semantic embedding quality.

| Mari index | Build | ANN Recall@10 | Corpus Recall@10 | Query p50 | Query p95 |
|---|---:|---:|---:|---:|---:|
| Dense flat | 1.3 ms | 1.0000 | 0.3906 | 0.24 ms | 0.26 ms |
| HNSW (`m=16`, `ef_search=64`) | 240 ms | 0.4391 | 0.2214 | 0.21 ms | 0.25 ms |
| IVF-PQ (32 lists, 8 probes, 8 subquantizers) | 46 ms | 0.2563 | 0.2318 | 1.11 ms | 1.37 ms |

The approximate-index defaults are not acceptable quality defaults. These results are a baseline for improving graph traversal, training, and parameter selection.

## Reproduce and audit

```console
python benchmarks/run_public.py all
python benchmarks/verify_results.py
```

`verify_results.py` independently recomputes the quality aggregates from all 962 committed case records and fails on a mismatch.
