[]{#procedural-learning}[Current]{.current-label}

# Procedural learning

## Promotion inputs

| Candidate outcome | Promotion policy |
|---|---|
| Improves held-out task score and passes safety gates | Submit for review |
| Improves score and regresses grounding or ACL isolation | Reject |
| Matches current behavior | Keep current version |
| Has training-set evidence | Require held-out evidence |

The included trace study exercises procedure mining on AgentBench-shaped
database interactions. Mari preserves the action order and applies the stated
promotion rules. Agent improvement requires an application-level evaluation.


:::{collapse} Promotion examples

| Candidate result | Grounding gate | ACL gate | Promotion outcome |
|---|---:|---:|---|
| Better task score | Pass | Pass | Submit for human review |
| Better task score | Fail | Pass | Reject |
| Better task score | Pass | Fail | Reject |
| Same task score | Pass | Pass | Retain active version |
:::



Execution feedback supplies evidence for a procedural update. Promotion reads
held-out results and prior failures. It also checks related procedures before
an explicit review.

## How it works

An application asks a model to examine a trajectory and its observed outcome.
Mari parses the response into atomic skillbook operations, then applies them to
a copy of the active version. Evaluation covers the target procedure and known
failures. Related procedures supply regression cases. Hard gates catch
grounding or ACL regressions. A passing report creates a review proposal.
Successful attempts keep one identity class. Failures use another. A partial
attempt carries its own record type.

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
    submit_for_review(candidate, report)  # application action
```

## Supporting mining functions

| Function | Role before promotion |
|---|---|
| `mine_trajectory_process(runs, activity_aliases=...)` | Shows repeated variants, transitions, parallel calls, and rework before a procedure is proposed |
| `mine_trajectory_invariants(..., minimum_support=1.0, minimum_applicable=2)` | Produces reviewable regularities from explicitly successful traces |
| `compare_trajectories(..., mode=..., matches=...)` | Measures candidate paths with caller-defined argument equivalence |
| `select_diverse_trajectories(vectors, limit=..., relevance=..., density=...)` | Selects behaviorally separated review cases from caller embeddings |

The functions return evidence and unmatched cases. The caller decides which
behavior is desirable. Activation happens through the application's commit
path.
