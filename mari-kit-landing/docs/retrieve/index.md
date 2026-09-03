# Retrieve

## Evaluation

| Feature | Evaluation | Result | Detail |
|---|---|---:|---|
| [BM25](retrieval.md#evaluation) | BEIR SciFact | nDCG@10 `0.6634` | Full test split |
| [Dense flat](retrieval.md#evaluation) | SciFact index slice | ANN Recall@10 `1.0000` | Exact oracle |
| [HNSW](retrieval.md#evaluation) | SciFact index slice | ANN Recall@10 `0.4391` | Current measured failure |
| [IVF-PQ](retrieval.md#evaluation) | SciFact index slice | ANN Recall@10 `0.2563` | Current measured failure |
| [Contradiction retrieval](contradiction-retrieval.md#evaluation) | Conformance | 6 / 6 pass | ContraDoc not measured |
| [Construction and adaptive retrieval](retrieval-construction.md#evaluation) | Conformance | 12 / 12 pass | Task corpora not measured |
| [Context assembly](context.md#evaluation) | Conformance | 7 / 7 pass | LongBench/QASPER not measured |

| Retrieval shape | Use |
|---|---|
| Lexical BM25 | Exact terminology, identifiers, and code symbols |
| Dense flat | Exact small-corpus baseline |
| HNSW / IVF-PQ | Approximate candidates with measured recall loss |
| MUVERA + MaxSim | Token-level multi-vector candidate generation and exact reranking |
| SparseCL | Same-topic contradiction candidates |
| Graph propagation | Multi-hop entity-to-passage recall |

:::{collapse} Actual ranking snapshot

| Query | Relevant document | BM25 rank | Approximate-index observation |
|---|---:|---:|---|
| SciFact `100` | `4381486` | 1 | Lexical retrieval succeeds immediately |
| SciFact `1099` | `7662206` | 3 | Relevant result follows two distractors |
| SciFact `1` | `31715818` | >100 | Current BM25 misses at evaluation depth |

The detailed page exposes complete top-five candidates and exact-versus-approximate overlap.
:::


```{toctree}
:maxdepth: 1

retrieval
contradiction-retrieval
retrieval-construction
adaptive-retrieval
context
```
