[]{#retrieval}[Current]{.current-label}

# Multi-vector retrieval

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
| [Proposed]{.pill .next} | Dense flat | Exact cosine, dot-product, or L2 scan over one vector per passage | Small corpora, evaluation baselines, or exact reproducibility | [Dense Passage Retrieval](https://arxiv.org/abs/2004.04906){.paper} |
| [Proposed]{.pill .next} | HNSW | Hierarchical proximity graph for approximate nearest-neighbor search | Large mutable dense-vector collections with low-latency queries | [HNSW](https://doi.org/10.1109/TPAMI.2018.2889473){.paper} |
| [Proposed]{.pill .next} | IVF-PQ | Coarse inverted partitions plus product-quantized vector codes | Memory-constrained or very large dense indexes | [Product Quantization](https://doi.org/10.1109/TPAMI.2010.57){.paper} · [Faiss](https://arxiv.org/abs/1702.08734){.paper} |
| [Proposed]{.pill .next} | BM25 | Probabilistic lexical ranking over an inverted term index | Exact names, identifiers, code symbols, and domain terminology | [BM25 and Beyond](https://doi.org/10.1561/1500000019){.paper} |
| [Proposed]{.pill .next} | Learned sparse | Transformer-produced sparse term weights served by an inverted index | Lexical interpretability with learned expansion | [SPLADE](https://arxiv.org/abs/2107.05720){.paper} |
| [Current]{.pill .live} | Rank fusion | Weighted reciprocal-rank fusion over independent result lists, with per-source contribution traces | Mixed corpora where source scores are not directly comparable | [RAG-Fusion](https://arxiv.org/abs/2402.03367){.paper} |
| [Current]{.pill .live} | Graph propagation | Allowed-node personalized PageRank followed by weighted node-to-passage projection | Multi-hop recall from query-linked entities, facts, or sections | [HippoRAG](https://arxiv.org/abs/2405.14831){.paper} |

## Proposed index interface

The common protocol should describe capabilities rather than a vendor. Index selection then becomes pipeline configuration and can be evaluated against recall, latency, memory, freshness, and ACL-filter behavior.

```{code-block} python
:caption: proposed / indexes.py

indexes = {
    "exact": DenseFlatIndex(metric="cosine"),
    "dense": HNSWIndex(metric="cosine", m=32, ef_search=128),
    "compressed": IVFPQIndex(partitions=4096, subquantizers=32),
    "lexical": BM25Index(k1=1.2, b=0.75),
    "sparse": SparseVectorIndex(model="splade"),
    "late": LateInteractionIndex(candidate="muvera", rerank="maxsim"),
}

hybrid = HybridIndex(arms=[indexes["lexical"], indexes["dense"], indexes["late"]],
    fusion=ReciprocalRankFusion(k=60))
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
