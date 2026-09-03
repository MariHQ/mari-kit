# Retrieve

## Choose a retrieval path


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
