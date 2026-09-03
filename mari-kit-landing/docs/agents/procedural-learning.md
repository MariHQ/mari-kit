[]{#procedural-learning}[Proposed]{.proposed-label}

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
:caption: proposed / skillbook.py

reflection = reflect(trajectory, outcome=outcome, evidence=observed_context)
patch = curate(reflection, operations={"ADD", "UPDATE", "TAG", "REMOVE"})
candidate = skillbook.apply_to_copy(patch)

gate = regression_gate(candidate, baseline=skillbook.active,
    suites=[own_cases, related_procedure_cases, known_failures],
    require={TaskSuccess(): NoRegression(), Groundedness(): AtLeast(0.95),
             ACLLeakage(): Exactly(0.0)})
if gate.passed:
        skillbook.propose(candidate, trace=gate.trace)  # human promotion remains explicit
```
