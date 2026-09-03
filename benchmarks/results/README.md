# Measured benchmark runs

These are recorded outputs from `python benchmarks/run_public.py all`, not target values or fixture tests. The corpus files are excluded from Git; each report pins the public artifact checksum, code commit, runtime, configuration, aggregate measurements, and environment. The adjacent JSONL contains every ranked case.

## Results

### Knowledge from experience

PlugMem's Apache-2.0 coding smoke fixture contains 3 sessions and 12 events.
Mari retained both post-tool outcomes: one explicit failure and one explicit
success. A separate four-run known-answer fixture associated `retry` with 2/2
failed and 0/2 successful runs (corrected risk ratio 5.00, 95% interval
0.38–66.01). The wide interval is material: this validates arithmetic and
evidence linkage, not production effect size.

### Knowledge boundary semantics

Five known-answer cases pass for exact observation-stage accounting,
derived-as-independent detection, conditional disclosure, coordinated edit
previews, and budgeted progressive expansion. The adjacent JSONL preserves
expected and observed values for every case. This is semantic conformance, not
an application-quality score.

### BEIR SciFact retrieval

Full public test split: 5,183 documents and 300 judged queries.

| Mari implementation | nDCG@10 | MRR@10 | Recall@10 | Recall@100 | Query p50 | Query p95 |
|---|---:|---:|---:|---:|---:|---:|
| BM25 (`k1=1.2`, `b=0.75`) | 0.6634 | 0.6309 | 0.7876 | 0.8826 | 57.97 ms | 68.76 ms |

### LongMemEval-S session retrieval

Full cleaned public small split: 500 questions, with the benchmark's 30 `_abs` cases excluded exactly as in the official evaluator. The 470 scored questions retrieve among roughly 50 timestamped sessions each. `Recall all` requires every evidence session to be present.

| Mari implementation | Recall all@5 | Recall all@10 | nDCG any@5 | nDCG any@10 | Query p50 | Query p95 |
|---|---:|---:|---:|---:|---:|---:|
| Session BM25 | 0.8298 | 0.9021 | 0.8835 | 0.8972 | 3.28 ms | 3.67 ms |

The weakest Recall all@10 categories are `multi-session` (0.8182), `temporal-reasoning` (0.8504), and `single-session-preference` (0.8667). The report retains all per-category measurements.

### SciFact-derived index comparison

Index-only run over 512 real SciFact documents and 64 judged queries. A fixed 128-dimensional signed feature hash holds the encoder constant. `ANN Recall@10` measures overlap with Mari's exact top ten; it does not claim semantic embedding quality.

| Mari index | Build | ANN Recall@10 | Corpus Recall@10 | Query p50 | Query p95 |
|---|---:|---:|---:|---:|---:|
| Dense flat | 1.1 ms | 1.0000 | 0.3906 | 0.24 ms | 0.25 ms |
| HNSW (`m=16`, `ef_search=64`) | 251 ms | 0.4391 | 0.2214 | 0.22 ms | 0.25 ms |
| IVF-PQ (32 lists, 8 probes, 8 subquantizers) | 38 ms | 0.2563 | 0.2318 | 1.16 ms | 1.32 ms |

The approximate-index defaults are not acceptable quality defaults. These results are a baseline for improving graph traversal, training, and parameter selection.

## Reproduce and audit

```console
python benchmarks/run_public.py all
python benchmarks/verify_results.py
```

`verify_results.py` independently recomputes the quality aggregates from all 962 committed case records and fails on a mismatch.

API conformance is recorded separately because passing deterministic cases is not corpus quality:

```console
python benchmarks/run_conformance.py
```

`documented-api-conformance.json` records the aggregate and the adjacent JSONL records every case and duration. Documentation pages link each research-derived mechanism to the relevant focused subset and state when no corpus score exists.
