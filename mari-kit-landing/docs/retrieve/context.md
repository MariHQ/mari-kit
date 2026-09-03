[]{#context}[Proposed]{.proposed-label}

# Retrieval plans and context envelopes

```{include} ../_includes/eval/retrieve.md
```

A retrieval plan would run explicit arms, fuse ranks, enforce scope and freshness, rerank, and pack a bounded context envelope. Its trace explains inclusion and exclusion.

## How it works

Run semantic, lexical, graph, and recency arms over authorized IDs. Convert arm scores to ranks and combine them with reciprocal-rank fusion, then discard stale dependencies, rerank survivors, diversify near-duplicates, and greedily pack whole evidence excerpts under token/document limits. The envelope contains rendered context plus source revisions and per-candidate include/exclude reasons, allowing the caller to reproduce what the model saw.

**Research basis**[RAG](https://arxiv.org/abs/2005.11401){.paper} motivates explicit, updateable non-parametric memory and provenance; [RAG-Fusion](https://arxiv.org/abs/2402.03367){.paper} and [MMR](https://www.cs.cmu.edu/afs/cs/Web/People/jgc/publication/MMR_DiversityBased_Reranking_SIGIR_1998.pdf){.paper} back fusion and diversity; [Lost in the Middle](https://arxiv.org/abs/2307.03172){.paper} makes budget and evidence order evaluation requirements. `ContextEnvelope` is Mari\'s proposed carrier for those observable decisions.

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
:caption: proposed / context.py

plan = RetrievalPlan(arms=[Semantic(vector_index, limit=40),
    Lexical(lexical_index, limit=30), GraphExpand(graph_index, hops=2),
    RecentChanges(window="14d")], fusion=ReciprocalRankFusion(k=60),
    reranker=ExactMaxSim())

context = assemble_context(query, plan=plan, scope=user.knowledge_scope,
    budget=ContextBudget(tokens=6000, documents=12))
model(context.render())
audit(context.retrieval_trace)
```
