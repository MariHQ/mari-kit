[]{#memory-evaluation}[Current]{.current-label}

# Long-horizon memory evaluation

## Evaluation

The measured LongMemEval-S run uses the complete cleaned small split. Following the official evaluator, 30 `_abs` questions are excluded and 470 are scored. Session BM25 reaches `0.8298` Recall-all@5, `0.9021` Recall-all@10, `0.8835` nDCG-any@5, and `0.8972` nDCG-any@10. Per-question rankings and per-capability results are committed, and an independent verifier recomputes every aggregate.

```console
$ python benchmarks/run_public.py longmemeval
$ python benchmarks/verify_results.py
verified 3 reports and 962 case records
```

This is a retrieval evaluation. End-to-end reader accuracy, write/update quality, and abstention accuracy are not yet measured.


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
