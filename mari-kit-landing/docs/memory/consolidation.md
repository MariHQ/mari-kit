[]{#consolidation}[Reference]{.current-label}

# Tiered memory consolidation

## Behavior

| Tier | Keep here when | Promotion signal |
|---|---|---|
| Working | Needed by the active task | Immediate relevance |
| Episodic | A specific event retained for later use | Reuse, outcome, or recency |
| Semantic | A stable fact is supported across evidence | Confidence, recurrence, and review |
| Procedural | A repeatable successful sequence exists | Held-out task improvement |

Consolidation is a budgeted selection policy. Summary generation, importance scoring, and promotion approval remain injected decisions.


:::{collapse} Example budget selection

| Candidate | Utility | Estimated tokens | Selected |
|---|---:|---:|---:|
| Refund-policy session | 0.91 | 2,400 | Yes |
| Duplicate refund discussion | 0.42 | 2,100 | No |
| Unrelated support session | 0.18 | 1,700 | No |
:::



Tiers are policies over cost and lifecycle. Mari provides topic segmentation and a deterministic promotion planner. The host supplies compression models and commits selected revisions, keeping raw observations available for audit.

## How it works

Filter observations cheaply, group them at attention-peak/similarity-valley topic boundaries, compress within bounded groups, and score promotion from recurrence, recency, usefulness, and evidence diversity. Expensive resolving, superseding, and summarization run in an offline call/token budget. Promotion creates a new artifact revision linked to every contributing observation.

`plan_consolidation` implements the selection step. It normalizes the four
weights, computes a weighted score, then processes candidates by descending
score with artifact ID as the tie-break. A candidate is selected when it meets
the minimum score and fits both remaining estimated budgets. This is a greedy
score-ordered policy. A cost-optimal knapsack solution can select a different
set. Deferred candidates include both low-score and over-budget items.

The plan reserves estimated work. Your executor must enforce actual usage and
handle retries. Represent summaries as derived artifacts with ordered source
membership, revisions, and summarizer configuration so
[dependency-aware updates](../start/dependency-updates.md) can reuse completed
consolidation work after unrelated changes.

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
:caption: Select promotions under explicit model-call and token budgets

from mari_components.knowledge import (
    ConsolidationBudget,
    PromotionSignal,
    plan_consolidation,
)

plan = plan_consolidation(
    [
        PromotionSignal(
            artifact_id="session:refunds",
            recurrence=0.9,
            recency=0.8,
            usefulness=0.95,
            evidence_diversity=0.7,
            estimated_calls=2,
            estimated_tokens=2400,
        )
    ],
    budget=ConsolidationBudget(max_model_calls=20, max_tokens=50_000),
    minimum_score=0.70,
)
assert plan.selected_ids == ("session:refunds",)
```
