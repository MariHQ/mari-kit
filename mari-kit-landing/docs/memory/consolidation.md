[]{#consolidation}[Partially current]{.proposed-label}

# Tiered memory consolidation

Tiers are policies over cost and lifecycle, not hard-coded stores. Topic segmentation is current; compression, promotion, and offline scheduling are proposed. Each promotion creates a dependency-bearing proposal, and raw observations remain available for audit.

## How it works

Filter observations cheaply, group them at attention-peak/similarity-valley topic boundaries, compress within bounded groups, and score promotion from recurrence, recency, usefulness, and evidence diversity. Expensive resolving, superseding, and summarization run in an offline call/token budget. Promotion creates a new artifact revision linked to every contributing observation.

::: source-block
**Papers**

[LightMem: topic-aware consolidation and offline updates](https://arxiv.org/abs/2510.18866){.paper}[MemoryOS: tiered agent memory](https://arxiv.org/abs/2506.06326){.paper}
:::

::::::{container} diagram promotion
<div>

**Observation buffer**[cheap filters · content hashes]{.small}

</div>

*topic boundary*

<div>

**Session groups**[bounded compression]{.small}

</div>

*offline window*

<div>

**Consolidated artifacts**[resolve · supersede · review]{.small}

</div>
::::::

```{code-block} python
:caption: proposed / consolidation.py

policy = ConsolidationPolicy(
    segment=TopicBoundary(window=12, threshold=0.68),
    promote=PromotionScore(recurrence=0.30, recency=0.15,
        usefulness=0.35, evidence_diversity=0.20),
    schedule=OfflineWindow(max_model_calls=20, max_tokens=50000))
plan = plan_consolidation(observations, policy=policy)
commit(review(plan.mutations), dependencies=plan.dependencies)
```
