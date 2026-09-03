[]{#context}[Current]{.current-label}

# Retrieval plans and context envelopes

## At a glance

| QASPER packing configuration | Observed result | Meaning |
|---|---:|---|
| 1,024-token, 12-document budget | Evidence recall `0.527` | About half of annotated evidence survived packing |
| Same run | Evidence density `0.117` | Most packed tokens were context rather than annotated evidence |
| Authorization filter | Leakage `0` | Unauthorized candidates are removed before ordering and rendering |

The first two values describe this BM25-backed configuration, not a universal context-window result. Adjust budget and ranking together.
Use the separate dimensions to identify the failure mode; do not treat high recall as evidence that a context is current or correctly ordered.

| Consumer probe | Evidence coverage | Other dimension | Decision consequence |
|---|---:|---:|---|
| Temporal research context | `1.000` | Temporal precision `0.667` | Perfect evidence recall still admitted a historical assertion |
| Code evidence retrieval | Recall `1.000` | MRR `0.500` | All relevant files appeared, but the first result was wrong |

:::{collapse} Worked inclusion trace

| Candidate | Authorized | Fresh | Fits budget | Decision |
|---|---:|---:|---:|---|
| `policy-current` | Yes | Yes | Yes | Included |
| `policy-stale` | Yes | No | Yes | Excluded: stale revision |
| `private-note` | No | Yes | Yes | Excluded before scoring |
| `appendix` | Yes | Yes | No | Excluded: token budget |
:::



Mari packs already-ranked retrieval candidates into a bounded, revision-bearing context envelope. Its trace explains every inclusion and exclusion.

## How it works

Run semantic, lexical, graph, and recency arms over authorized IDs. Convert arm scores to ranks and combine them with reciprocal-rank fusion, then discard stale dependencies, rerank survivors, diversify near-duplicates, and greedily pack whole evidence excerpts under token/document limits. The envelope contains rendered context plus source revisions and per-candidate include/exclude reasons, allowing the caller to reproduce what the model saw.

**Research basis**[RAG](https://arxiv.org/abs/2005.11401){.paper} motivates explicit, updateable non-parametric memory and provenance; [RAG-Fusion](https://arxiv.org/abs/2402.03367){.paper} and [MMR](https://www.cs.cmu.edu/afs/cs/Web/People/jgc/publication/MMR_DiversityBased_Reranking_SIGIR_1998.pdf){.paper} back fusion and diversity; [Lost in the Middle](https://arxiv.org/abs/2307.03172){.paper} makes budget and evidence order evaluation requirements. `ContextEnvelope` is Mari\'s carrier for those observable decisions.

::::::{container} diagram context
::: arms
semanticlexicalgraphrecent
:::

*RRF*

<div>

**authorizefreshnessrerank**

</div>

*budget*

<div>

**ContextEnvelope**[excerpts · evidence · revisions · trace]{.small}

</div>
::::::

```{code-block} python
:caption: context.py

from mari_components.retrieval import ContextBudget, ContextCandidate, assemble_context

context = assemble_context([
    ContextCandidate(document_id=hit.document_id, revision=revisions[hit.document_id],
        text=passages[hit.document_id], token_count=token_count(hit.document_id),
        score=hit.score, authorized=can_read(hit.document_id),
        fresh=is_fresh(hit.document_id))
    for hit in fused_hits
], budget=ContextBudget(tokens=6000, documents=12))

model(context.text)
audit(context.trace)
```

## Artifact-neutral composition

`hydrate_hits` preserves rank, score, misses, and resolver failures while
joining index IDs to revisioned `RetrievalUnit` values. `select_context` then
packs those units under any set of caller-named budgets. The selection trace
retains every eligibility or budget rejection.

```{code-block} python
:caption: Hydrate ranked units and apply token and latency budgets

from mari_components.retrieval import (
    ContextItem, hydrate_hits, select_context,
)

hydrated = hydrate_hits(
    hits,
    identity=lambda hit: hit.document_id,
    score=lambda hit: hit.score,
    resolve=unit_store.get,
)

selection = select_context(
    [ContextItem(
        unit=hit.unit,
        score=hit.score,
        costs={"tokens": count_tokens(hit.unit.text), "latency_ms": 2},
        eligible=valid_at_query_time(hit.unit),
        exclusion_reasons=() if valid_at_query_time(hit.unit) else ("historical",),
    ) for hit in hydrated if hit.unit is not None],
    limits={"tokens": 6000, "latency_ms": 30},
)

model(selection.render())
validate_answer(visible_refs=selection.visible_refs)
```

The greedy packer is one inspectable reference algorithm, not a mandated
context policy. Token, byte, latency, and monetary costs have no built-in
priority; their names and limits come from the caller.
