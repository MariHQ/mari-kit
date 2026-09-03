[]{#memory-evaluation}[Current]{.current-label}

# Long-horizon memory evaluation

## At a glance

| Retrieval depth | Complete evidence recall | Any-evidence nDCG |
|---|---:|---:|
| 5 sessions | `0.830` | `0.884` |
| 10 sessions | `0.902` | `0.897` |

Moving from five to ten sessions mainly helps questions whose answer spans several conversations. The table below shows where the remaining failures concentrate.


| Question type | Questions | Recall-all@5 | Recall-all@10 |
|---|---:|---:|---:|
| Knowledge update | 72 | 0.9444 | 0.9861 |
| Multi-session | 121 | 0.6364 | 0.8182 |
| Single-session assistant | 56 | 1.0000 | 1.0000 |
| Single-session preference | 30 | 0.8667 | 0.8667 |
| Single-session user | 64 | 1.0000 | 1.0000 |
| Temporal reasoning | 127 | 0.7795 | 0.8504 |

:::{collapse} Actual complete-versus-partial retrieval

| Question ID | Type | Required sessions | Required-session ranks | Recall-all@5 |
|---|---|---:|---|---:|
| `e47becba` | Single-session user | 1 | `2` | 1.0 |
| `6d550036` | Multi-session | 4 | `4`, `8`, `>10`, `>10` | 0.0 |

The second ranking finds relevant evidence but not the complete multi-session set. This is why the page reports `Recall-all`, not only `Recall-any`.
:::



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
