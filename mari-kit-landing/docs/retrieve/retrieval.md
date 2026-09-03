[]{#retrieval}[Current]{.current-label}

# Multi-vector retrieval

## At a glance

| Approach | What the current measurements suggest |
|---|---|
| BM25 | Strong lexical baseline on SciFact: nDCG@10 `0.663`, Recall@100 `0.883` |
| Learned sparse | Similar recall with TF-IDF weights (`0.888`); the caller's weight producer determines quality |
| Dense flat | Exact ranking reference for a chosen encoder |
| HNSW | `0.439` top-10 overlap with exact search; increase search breadth when recall matters |
| IVF-PQ | `0.256` overlap at this compression; choose it for memory savings, not exact ranking |
| MUVERA + MaxSim | `0.341` overlap; candidate budget and token embeddings need tuning |
| Rank fusion | A weak dense arm lowered nDCG@10 from `0.663` to `0.414`; fusion is not automatically better |

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

### Multi-vector late interaction

MUVERA compresses a set of token vectors into fixed-dimensional encodings for candidate search. Mari then applies exact ColBERT-style MaxSim to those candidates: each query token selects its strongest document-token match and the matches are summed. Choose this when token-level distinctions justify a larger index and a reranking stage. [MUVERA](https://arxiv.org/abs/2405.19504){.paper} · [ColBERT](https://arxiv.org/abs/2004.12832){.paper}

### Dense flat search

Dense flat search compares the query with every passage vector using cosine, dot product, or L2 distance. It costs a full scan, but introduces no approximation error, so it is the reference for deciding how much recall an approximate index loses. [Dense Passage Retrieval](https://arxiv.org/abs/2004.04906){.paper}

### HNSW

HNSW stores vectors in layered proximity graphs. Search begins in sparse upper layers and descends into denser neighborhoods; `ef_search` controls how many candidates remain active. Higher breadth generally improves recall at the cost of more distance calculations. [HNSW](https://doi.org/10.1109/TPAMI.2018.2889473){.paper}

### IVF-PQ

IVF first assigns vectors to coarse partitions and searches only selected partitions. Product quantization stores each residual as short codebook indexes instead of a full vector. More probes and larger codebooks improve fidelity while increasing latency and memory. [Product Quantization](https://doi.org/10.1109/TPAMI.2010.57){.paper} · [Faiss](https://arxiv.org/abs/1702.08734){.paper}

### BM25 and learned sparse vectors

BM25 scores exact term matches with term-frequency saturation and document-length normalization. Learned-sparse search uses the same inverted-index shape but accepts model-produced term weights, allowing vocabulary expansion without coupling Mari to a training framework. Use lexical retrieval for names, identifiers, and domain terms; use learned sparse vectors when an upstream model can justify the added complexity. [BM25 and Beyond](https://doi.org/10.1561/1500000019){.paper} · [SPLADE](https://arxiv.org/abs/2107.05720){.paper}

### Rank fusion

Reciprocal-rank fusion converts each result list to rank contributions and sums them, avoiding calibration between unrelated score scales. It works best when the arms retrieve complementary relevant material; adding a weak or redundant arm can make the final order worse. Mari retains each arm's contribution so that change is inspectable. [RAG-Fusion](https://arxiv.org/abs/2402.03367){.paper}

### Graph propagation

Personalized PageRank starts probability mass at query-linked nodes, repeatedly follows allowed graph edges, and projects the resulting node scores back to passages. It can recover multi-hop context that text retrieval misses, but only if entity links and authorization filters are reliable. [HippoRAG](https://arxiv.org/abs/2405.14831){.paper}

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

BM25 accepts a caller analyzer and produces per-term score contributions.
`with_deltas` returns a new snapshot after revision-checked upserts and deletes,
so a streaming change need not silently rebuild from unversioned input.

```{code-block} python
:caption: Explain and incrementally replace one lexical unit

from mari_components.retrieval import IndexDelta, IndexOperation

lexical = BM25Index(
    passages,
    analyzer=domain_analyzer,
    revisions=passage_revisions,
)
why = lexical.explain("refund window", item_id="policy#returns")

lexical = lexical.with_deltas([IndexDelta(
    item_id="policy#returns",
    operation=IndexOperation.UPSERT,
    text="Returns are accepted within 14 days.",
    expected_revision="v7",
    revision="v8",
)])
```

| Explanation field | Meaning |
|---|---|
| `term_frequency` | Matches emitted by the injected analyzer in this unit |
| `inverse_document_frequency` | Corpus rarity at this immutable snapshot |
| `score` | This query term's contribution after length normalization |

`ArtifactBM25Index` accepts `ArtifactRef` keys and returns `ArtifactIndexHit`
values. Multiple immutable revisions therefore remain distinct without encoding
`artifact@revision#unit` into a field named `document_id`.

```{code-block} python
:caption: Search immutable artifact revisions directly

from mari_components.retrieval import (
    ArtifactBM25Index, ArtifactIndexDelta, IndexOperation,
)

index = ArtifactBM25Index({unit.ref: unit.text for unit in retrieval_units})
hits = index.search(query, limit=10, allowed_refs=applicable_refs)
why = index.explain(query, ref=hits[0].ref)

index = index.with_deltas([ArtifactIndexDelta(
    ref=current_ref,
    previous_ref=prior_ref,
    operation=IndexOperation.UPSERT,
    text=current_text,
)])
```

`previous_ref` is an exact optimistic revision check. Mari replaces only that
unit; it does not infer which of several indexed manifestations is canonical.

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
