[]{#memory-evaluation}[Reference]{.current-label}

# Long-horizon memory evaluation

Retrieval-oriented memory corpora locate failures inside the knowledge system.
Task-level comparisons measure application outcomes after a change.

## LongMemEval result

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

The second ranking finds part of the relevant evidence. Some required sessions
fall below rank ten. `Recall-all` records that incomplete set. `Recall-any`
would score the same query from its first relevant hit.
:::



A memory evaluation measures each operation through its own output. Write-time
scores cover extraction and updates. Retrieval metrics inspect evidence ranks.
Temporal questions exercise ordering and date logic. Abstention cases contain
missing evidence. Token counts capture pressure from the context limit. Keeping
these fields separate locates the subsystem behind a failed answer.

## How it works

Freeze conversations and source revisions into cases. Each case also records
expected evidence and change events. Replay it under the corpus size and
context budget named in the run configuration. Score extraction during writes.
At query time, record evidence recall and cross-session synthesis. Separate
fields cover temporal reasoning, updates, abstention, and ACL leakage. Store a
trace beside each score. A regression can then point to the parser, index,
policy, or packing decision that produced it.

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

[LongMemEval: five long-term memory capabilities](https://arxiv.org/abs/2410.10813){.paper}[STATE-Bench](https://github.com/microsoft/STATE-Bench){.paper}[AgentMemBench](https://github.com/mazaiying/AgentMemBench){.paper}

[The adapter, deterministic metrics, run identity, and hard regression gates are implemented. System execution remains an injected application callback.]{.small}
:::

## Compare application outcomes

STATE-Bench evaluates 450 stateful tasks across customer support, travel, and
shopping. Cases contain deterministic assertions and policy checks. They also
measure user interaction and efficiency. Run the same task with a fixed agent
configuration for each knowledge strategy. Pair results by task ID.

```{code-block} python
:caption: Compare paired variants across separate measures

from mari_components.evaluation import TaskOutcome, compare_task_outcomes

comparison = compare_task_outcomes(
    baseline=(TaskOutcome(task_id="return-17", success=False, turns=9, tokens=8_400),),
    candidate=(TaskOutcome(task_id="return-17", success=True, turns=6, tokens=6_100),),
)

print(comparison.success_delta)   # 1.0 for this one-task example
print(comparison.mean_token_delta)  # -2300.0
```

| Measure | Keep separate because |
|---|---|
| Task success | Retrieval quality and application success have separate fields |
| Policy compliance | Answer speed and policy compliance have separate fields |
| Interaction quality | Correct work can impose unnecessary user effort |
| Turns and tool calls | Measure the change in operational work |
| Context and total tokens | Retrieval savings can be offset by memory maintenance |
| Memory write/retrieval cost | Agent tokens and memory-system tokens have different causes |
