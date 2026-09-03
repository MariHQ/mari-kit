[]{#context}[Current]{.current-label}

# Retrieval plans and context envelopes

## Evaluation

The current context evaluation contains one deterministic case that verifies authorization and freshness filtering, whole-excerpt packing, budget enforcement, and exclusion traces. Six retrieval-composition cases separately cover RRF, MMR, and graph propagation. No LongBench or QASPER answer score has been run; the RAG, RAG-Fusion, MMR, and Lost-in-the-Middle citations support mechanisms only.

```console
$ pytest -q tests/test_context.py tests/test_retrieval_algorithms.py
7 passed
```


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
