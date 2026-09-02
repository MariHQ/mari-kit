# Research-derived knowledge algorithms

These modules implement deterministic algorithm boundaries from four papers.
They do not own model calls, databases, embedding providers, entity extraction,
or authorization. A host supplies those inputs; Mari validates, orders, and
returns immutable plans or scores.

## Retrieval flow

```text
dense ranks ───┐
lexical ranks ─┼─ reciprocal_rank_fusion ─ maximal_marginal_relevance ─ context
graph ranks ───┘                 ▲
                                │
query-linked seeds ─ personalized_pagerank ─ project_graph_scores
```

Apply tenant, ACL, and time filters before rank fusion or graph propagation.
`reciprocal_rank_fusion` provides an `eligible` boundary for ranked lists;
`personalized_pagerank` builds the induced `allowed_node_ids` graph before it
normalizes edges.

### Reciprocal-rank fusion

`reciprocal_rank_fusion` combines ranks without requiring comparable source
scores. Each source contributes `weight / (rank_constant + rank)`. Ranks are
one-based, duplicate IDs contribute once per source, and final ties break by
document ID. Every result retains its per-source contribution.

```python
from mari_components.retrieval import reciprocal_rank_fusion

hits = reciprocal_rank_fusion(
    {
        "muvera": ["refunds", "billing", "terms"],
        "lexical": ["terms", "refunds", "faq"],
        "recent": ["refunds", "changelog"],
    },
    weights={"muvera": 1.0, "lexical": 1.0, "recent": 0.25},
    rank_constant=60,
    eligible=authorized_document_ids.__contains__,
    limit=40,
)

for hit in hits:
    audit(hit.document_id, hit.score, hit.contributions)
```

Source: [RAG-Fusion](https://arxiv.org/abs/2402.03367), which applies
reciprocal-rank fusion to results from multiple generated queries; the original
fusion method is described in [Cormack, Clarke, and Buettcher
(2009)](https://doi.org/10.1145/1571941.1572114).

### Maximal marginal relevance

`maximal_marginal_relevance` greedily balances relevance with the maximum
similarity to anything already selected:

```text
MMR(d) = lambda * relevance(d) - (1 - lambda) * max similarity(d, selected)
```

```python
from mari_components.retrieval import maximal_marginal_relevance

packed = maximal_marginal_relevance(
    {hit.document_id: hit.score for hit in hits},
    similarity=lambda left, right: cosine(vectors[left], vectors[right]),
    relevance_weight=0.65,
    limit=12,
)
```

The similarity function is injected so callers can diversify by embeddings,
source, topic, or any composite measure. Selection is deterministic; ties use
relevance and then document ID. Source: [Carbonell and Goldstein
(1998)](https://www.cs.cmu.edu/afs/cs/Web/People/jgc/publication/MMR_DiversityBased_Reranking_SIGIR_1998.pdf).

### Personalized PageRank graph recall

`personalized_pagerank` performs weighted power iteration from caller-supplied
seeds. Dangling mass returns to the seed distribution. `PageRankResult` exposes
the iteration count and convergence state instead of hiding budget exhaustion.
`project_graph_scores` then multiplies node probability by a caller-supplied
node-to-passage incidence map.

```python
from mari_components.retrieval import personalized_pagerank, project_graph_scores

recall = personalized_pagerank(
    graph={
        "refund": {"enterprise-plan": 1.0},
        "enterprise-plan": {"thirty-days": 1.0},
    },
    seeds={"refund": 1.0},
    damping=0.85,
    allowed_node_ids=authorized_graph_nodes,
)

passages = project_graph_scores(
    recall.hits,
    node_passages={
        "refund": {"policy-intro": 1.0},
        "thirty-days": {"enterprise-terms": 2.0},
    },
    limit=20,
)
assert recall.converged
```

The graph is directed; add reverse edges explicitly when relations should be
traversable both ways. Incidence weights can represent entity occurrence
counts. Source: [HippoRAG](https://arxiv.org/abs/2405.14831), sections 2.2–2.3.

## Memory update flow

```text
observations ─ hybrid_topic_segments ─ host extraction/classification
                                              │
current store + candidates + decisions ─ plan_memory_mutations ─ host commit
                                              │
                                    apply_memory_mutations
                                    (pure preview/testing)
```

### Four-operation memory reconciliation

The update classifier stays outside Mari. It can be a model, rules engine, or
review UI. Mari joins decisions to candidate IDs and rejects missing decisions,
unknown candidates, absent update/delete targets, add collisions, and multiple
operations against the same target.

```python
from mari_components.knowledge import (
    MemoryDecision,
    MemoryOperation,
    apply_memory_mutations,
    plan_memory_mutations,
)

plan = plan_memory_mutations(
    existing={"role": "Sam works at A", "tool": "Sam uses X"},
    candidates={"new-role": "Sam works at B", "left-tool": "Sam stopped using X"},
    decisions={
        "new-role": MemoryDecision(
            operation=MemoryOperation.UPDATE,
            target_id="role",
            reason="newer explicit statement",
        ),
        "left-tool": MemoryDecision(
            operation=MemoryOperation.DELETE,
            target_id="tool",
            reason="explicit contradiction",
        ),
    },
)

preview = apply_memory_mutations(current_values, plan)
storage.commit(plan, expected_generation=current_generation)
```

`apply_memory_mutations` returns a new dictionary and never mutates its input.
It is a preview/reference projector, not a persistence layer. Source:
[Mem0](https://arxiv.org/abs/2504.19413), section 2.1 and appendix algorithm 1.

### Hybrid topic segmentation

`hybrid_topic_segments` intersects two boundary signals. A split is emitted
only when cross-item attention is an interior local maximum and adjacent
semantic similarity is below the configured threshold.

```python
from mari_components.knowledge import hybrid_topic_segments

segments = hybrid_topic_segments(
    turns,
    attention_boundaries=[0.12, 0.91, 0.20, 0.43],
    adjacent_similarities=[0.88, 0.21, 0.72, 0.66],
    similarity_threshold=0.40,
)

for segment in segments:
    proposals = extract_memory_candidates(segment.items)
    enqueue_for_offline_reconciliation(proposals)
```

Both signal arrays describe the `len(items) - 1` gaps between adjacent items.
Short inputs and inputs with no joint boundary produce one segment. Source:
[LightMem](https://arxiv.org/abs/2510.18866), section 3.1.

## What is and is not implemented

| Paper | Implemented in Mari | Supplied by the application |
|---|---|---|
| RAG-Fusion | weighted RRF, deduplication, eligibility, contribution trace | query generation and each retrieval arm |
| HippoRAG | weighted personalized PageRank, induced-node filtering, convergence report, passage projection | OpenIE/entity extraction, entity linking, graph persistence |
| Mem0 | validated ADD/UPDATE/DELETE/NOOP plan and pure projection | fact extraction and semantic operation classification |
| LightMem | hybrid attention/similarity topic boundaries | compression, attention/embedding models, summaries, offline scheduling |

The package implements the reusable backing algorithms, not each paper's full
application architecture or experimental model stack.
