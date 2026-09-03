[]{#procedural-learning}[Current evaluation boundary]{.current-label}

# Procedural learning and regression gates

```{include} ../_includes/eval/agents.md
```

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
