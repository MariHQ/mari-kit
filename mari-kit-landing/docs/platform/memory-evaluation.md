[]{#memory-evaluation}[Current]{.current-label}

# Long-horizon memory evaluation

```{include} ../_includes/eval/platform.md
```

A memory system needs separate measurements for writing, updating, retrieving, temporal reasoning, abstaining, and respecting context limits. One aggregate answer score hides which subsystem failed.

## How it works

Freeze conversations, source revisions, expected evidence, and change events into cases. Replay each case under several corpus sizes and context budgets. Score extraction at write time, evidence recall at query time, cross-session synthesis, ordering and date reasoning, correction after source updates, abstention when evidence is absent, and ACL leakage. Store per-stage traces with every score so a regression points to the responsible parser, index, policy, or packing decision.

::::::::: metric-grid
<div>

**Extraction**precision · recall · evidence

</div>

<div>

**Retrieval**recall@k · rank · authorization

</div>

<div>

**Synthesis**support · completeness

</div>

<div>

**Temporal**order · valid time · updates

</div>

<div>

**Abstention**unsupported-answer rate

</div>

<div>

**Operations**tokens · latency · refresh work

</div>
:::::::::

```{code-block} python
:caption: Adapt LongMemEval cases and persist a reproducible run identity

from datetime import datetime, timezone

from mari_components.evaluation import EvaluationRun, load_longmemeval_cases

cases = load_longmemeval_cases("data/longmemeval_s.json")
metrics = evaluate_memory_cases(system, cases)  # application-owned execution

run = EvaluationRun(
    run_id="memory-main-0042",
    corpus_id="longmemeval",
    corpus_revision="sha256:...",
    split="longmemeval_s",
    mari_revision="git:...",
    started_at=datetime.now(timezone.utc),
    configuration={"context_budget": 8_000},
    model_identifiers=("reader@2026-08",),
    seed=7,
    metrics=metrics,
)
```

::: source-block
**Paper**

[LongMemEval: five long-term memory capabilities](https://arxiv.org/abs/2410.10813){.paper}

[The adapter, deterministic metrics, run identity, and hard regression gates are implemented. System execution remains an injected application callback.]{.small}
:::
