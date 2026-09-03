[]{#consolidation}[Current]{.current-label}

# Tiered memory consolidation

## Evaluation

| Evaluation | Cases | Result | Corpus result |
|---|---:|---:|---|
| Budgeted deterministic selection | 1 | 1 / 1 pass | — |
| Admission and temporal prerequisites | 3 | 3 / 3 pass | — |
| LightMem and MemoryOS end-to-end quality | — | Not run | Memory accuracy unavailable |

:::{collapse} Worked budget selection

| Candidate | Utility | Estimated tokens | Selected |
|---|---:|---:|---:|
| Refund-policy session | 0.91 | 2,400 | Yes |
| Duplicate refund discussion | 0.42 | 2,100 | No |
| Unrelated support session | 0.18 | 1,700 | No |
:::

### Reproduce

```console
$ pytest -q tests/test_governed_memory.py
```


Tiers are policies over cost and lifecycle, not hard-coded stores. Mari provides topic segmentation and a deterministic promotion planner. The host supplies compression models and commits selected revisions, keeping raw observations available for audit.

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
