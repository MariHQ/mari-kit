[]{#procedural-learning}[Current]{.current-label}

# Procedural learning

## At a glance

| Candidate outcome | Promotion policy |
|---|---|
| Improves held-out task score and passes safety gates | Submit for review |
| Improves score but regresses grounding or ACL isolation | Reject |
| Matches current behavior without improvement | Keep current version |
| Has only training-set evidence | Do not promote |

The included trace study exercises procedure mining on AgentBench-shaped database interactions. It shows that Mari preserves ordered actions and promotion rules; it does not establish that a procedure improves an application's agent.


:::{collapse} Worked promotion outcomes

| Candidate result | Grounding gate | ACL gate | Promotion outcome |
|---|---:|---:|---|
| Better task score | Pass | Pass | Submit for human review |
| Better task score | Fail | Pass | Reject |
| Better task score | Pass | Fail | Reject |
| No regression but no improvement | Pass | Pass | Retain active version |
:::



Execution feedback can propose procedural updates, but promotion depends on held-out cases, negative outcomes, cross-procedure interference, and explicit review.

## How it works

Reflect over a trajectory and observed outcome, turn the reflection into atomic add/update/tag/remove operations, and apply the patch to a copy of the active skillbook. Evaluate that candidate on its own cases, related-procedure cases, and known failures. Hard gates reject grounding or ACL regressions; passing creates a review proposal rather than activating it automatically. Worked, failed, and partial attempts remain separately retrievable.

::: source-block
**Papers**

[Agentic Context Engineering: incremental skillbooks](https://arxiv.org/abs/2510.04618){.paper}[Reflexion: learning from verbal feedback](https://arxiv.org/abs/2303.11366){.paper}[LongMemEval: long-horizon memory evaluation](https://arxiv.org/abs/2410.10813){.paper}
:::

```{code-block} python
:caption: Require independent quality and safety gates before review

from mari_components.evaluation import GateMode, MetricGate, regression_gate

report = regression_gate(
    {"task_success": 0.86, "groundedness": 0.97, "acl_leakage": 0.0},
    baseline={"task_success": 0.84},
    gates=[
        MetricGate(metric="task_success", mode=GateMode.NO_REGRESSION),
        MetricGate(metric="groundedness", mode=GateMode.AT_LEAST, value=0.95),
        MetricGate(metric="acl_leakage", mode=GateMode.AT_MOST, value=0.0),
    ],
)
if report.passed:
    submit_for_review(candidate, report)  # application action, never automatic
```

## Supporting mining functions

| Function | Role before promotion |
|---|---|
| `mine_trajectory_process(runs, activity_aliases=...)` | Shows repeated variants, transitions, parallel calls, and rework before a procedure is proposed |
| `mine_trajectory_invariants(..., minimum_support=1.0, minimum_applicable=2)` | Produces reviewable regularities from explicitly successful traces only |
| `compare_trajectories(..., mode=..., matches=...)` | Measures candidate paths against a reference without assuming one exact argument representation |
| `select_diverse_trajectories(vectors, limit=..., relevance=..., density=...)` | Selects behaviorally separated review cases from caller embeddings |

These functions expose evidence and unmatched cases. They do not decide that a
frequent behavior is desirable or that a procedure should be activated.
