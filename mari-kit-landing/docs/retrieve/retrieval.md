[]{#retrieval}[Current]{.current-label}

# Multi-vector retrieval

## Evaluation

| Run | Corpus | Scope | Metric | Result |
|---|---|---:|---|---:|
| BM25 | BEIR SciFact test | 5,183 documents; 300 queries | nDCG@10 | 0.6634 |
| BM25 | BEIR SciFact test | 5,183 documents; 300 queries | Recall@100 | 0.8826 |
| Dense flat | SciFact index slice | 512 documents; 64 queries | ANN Recall@10 | 1.0000 |
| HNSW | SciFact index slice | 512 documents; 64 queries | ANN Recall@10 | 0.4391 |
| IVF-PQ | SciFact index slice | 512 documents; 64 queries | ANN Recall@10 | 0.2563 |
| MUVERA, sparse, fusion, graph | Deterministic cases | API boundary | Corpus quality | Not measured |

The index slice uses one fixed 128-dimensional feature-hashing encoder, making dense flat the exact ranking oracle. The approximate-index rows are measured failures, not production recommendations.

:::{collapse} Actual SciFact ranking differences

| Query | Relevant document | BM25 rank | Top BM25 documents |
|---|---:|---:|---|
| `100` — hematopoietic stem-cell chromosome segregation | `4381486` | 1 | `4381486`, `4398832`, `2547636`, `15728433`, `25516011` |
| `1099` — statins and blood cholesterol | `7662206` | 3 | `21557614`, `22420524`, `7662206`, `7454794`, `9617381` |
| `1179` — the central domain of MDA5 | `31272411` | 10 | `10627801`, `1569031`, `16058322`, `2566674`, `52095986`, … |
| `1` — inductive properties of zero-dimensional biomaterials | `31715818` | >100 | `43385013`, `10608397`, `40212412`, `10931595`, `27049238` |

For query `1`, approximate search also changes the candidate set:

| Index | First five document IDs | Exact top-10 overlap |
|---|---|---:|
| Dense flat | `1263446`, `10670430`, `11674596`, `10365787`, `11369420` | 10 / 10 |
| HNSW | `10365787`, `10009203`, `11484808`, `10190778`, `10518721` | 2 / 10 |
| IVF-PQ | `11862753`, `11822354`, `11090688`, `10534299`, `12486491` | 1 / 10 |
:::

### Reproduce

```console
$ python benchmarks/run_public.py scifact
$ python benchmarks/run_public.py indexes
$ pytest -q tests/test_retrieval.py tests/test_index_families.py tests/test_retrieval_algorithms.py
```


Mari implements MUVERA fixed-dimensional candidate generation, PolarQuant compression, and exact normalized MaxSim reranking in one retrieval path.

::::::{container} diagram retrieval
<div>

**Query token vectors**

</div>

*MUVERA*

<div>

**Candidate documents**[allowed IDs only]{.small}

</div>

*exact MaxSim*

<div>

**RetrievalHit\[\]**[ranked + scored]{.small}

</div>
::::::

```{code-block} python
:caption: retrieve.py

from mari_components.retrieval import FDEConfig, build_index, search_index

index = build_index({doc.document_id: token_vectors},
    config=FDEConfig(repetitions=20, projection_dimension=16))
hits = search_index(index, query_token_vectors, limit=8,
    allowed_document_ids=authorized_document_ids)
```

`serialize_index` and `deserialize_index` use versioned, checksummed payloads. `exact_maxsim` is public for direct scoring.

**Authorization must precede scoring.** Supply `allowed_document_ids`; post-filtering can leak information through ranks and fallback behavior.

## How it works and backing algorithms

Mari\'s current path uses token-level late interaction: each query token takes its maximum similarity to any document token, and the maxima are summed. MUVERA maps those multi-vector sets to fixed-dimensional encodings for fast candidate generation; Mari then reranks the candidates with exact MaxSim. The packed Polar codec is an implementation-level compression of candidate encodings, not an alternative relevance model.

| Status | Index family | Representation and algorithm | Appropriate when | Primary source |
|----|----|----|----|----|
| [Current]{.pill .live} | MUVERA + exact MaxSim | Multi-vector FDE candidate generation, compressed storage, exact late-interaction reranking | Fine-grained semantic matching where individual query terms matter | [MUVERA](https://arxiv.org/abs/2405.19504){.paper} · [ColBERT](https://arxiv.org/abs/2004.12832){.paper} |
| [Current]{.pill .live} | Dense flat | Exact cosine, dot-product, or L2 scan over one vector per passage | Small corpora, evaluation baselines, or exact reproducibility | [Dense Passage Retrieval](https://arxiv.org/abs/2004.04906){.paper} |
| [Current]{.pill .live} | HNSW | Deterministic hierarchical proximity graph with configurable search breadth | Approximate dense search and recall-versus-exact evaluation | [HNSW](https://doi.org/10.1109/TPAMI.2018.2889473){.paper} |
| [Current]{.pill .live} | IVF-PQ | Coarse inverted partitions plus residual product-quantized vector codes | Memory-constrained dense indexes | [Product Quantization](https://doi.org/10.1109/TPAMI.2010.57){.paper} · [Faiss](https://arxiv.org/abs/1702.08734){.paper} |
| [Current]{.pill .live} | BM25 | Robertson--Walker lexical ranking over an in-memory inverted representation | Exact names, identifiers, code symbols, and domain terminology | [BM25 and Beyond](https://doi.org/10.1561/1500000019){.paper} |
| [Current]{.pill .live} | Learned sparse | Exact sparse inner product over caller-produced term weights | Model-neutral serving for SPLADE-like expansion vectors | [SPLADE](https://arxiv.org/abs/2107.05720){.paper} |
| [Current]{.pill .live} | Rank fusion | Weighted reciprocal-rank fusion over independent result lists, with per-source contribution traces | Mixed corpora where source scores are not directly comparable | [RAG-Fusion](https://arxiv.org/abs/2402.03367){.paper} |
| [Current]{.pill .live} | Graph propagation | Allowed-node personalized PageRank followed by weighted node-to-passage projection | Multi-hop recall from query-linked entities, facts, or sections | [HippoRAG](https://arxiv.org/abs/2405.14831){.paper} |

## Index interfaces

The index classes expose the same authorization-aware search shape while retaining algorithm-specific controls. Index selection is pipeline configuration and can be evaluated against recall, latency, memory, freshness, and ACL-filter behavior.

```{code-block} python
:caption: indexes.py

from mari_components.retrieval import (
    BM25Index, DenseFlatIndex, HNSWIndex, IVFPQIndex, SparseVectorIndex,
)

exact = DenseFlatIndex(vectors, metric="cosine")
graph = HNSWIndex(vectors, metric="cosine", m=32)
compressed = IVFPQIndex(vectors, partitions=256, subquantizers=16)
lexical = BM25Index(passages, k1=1.2, b=0.75)
sparse = SparseVectorIndex(model_generated_term_weights)

hits = graph.search(query_vector, limit=20, ef_search=128,
    allowed_document_ids=authorized_document_ids)
```

## Rank fusion, graph recall, and diverse packing

::::::{container} diagram context
::: arms
MUVERAlexicalrecent
:::

*RRF*

<div>

**authorized nodesPageRankpassage projection**

</div>

*MMR*

<div>

**Context candidates**[scores and contributions retained]{.small}

</div>
::::::

```{code-block} python
:caption: compose_retrieval.py

from mari_components.retrieval import (
    maximal_marginal_relevance, personalized_pagerank,
    project_graph_scores, reciprocal_rank_fusion,
)

fused = reciprocal_rank_fusion(
    {"muvera": dense_ids, "lexical": lexical_ids, "recent": recent_ids},
    weights={"recent": 0.25}, rank_constant=60,
    eligible=authorized_document_ids.__contains__, limit=40)

nodes = personalized_pagerank(graph, query_seeds,
    allowed_node_ids=authorized_graph_nodes, damping=0.85)
passages = project_graph_scores(nodes.hits, node_passages, limit=20)

context = maximal_marginal_relevance(
    {hit.document_id: hit.score for hit in fused},
    similarity=passage_similarity, relevance_weight=0.65, limit=12)
assert nodes.converged
```
