[]{#procedures}[Current]{.current-label}

# Procedural knowledge

## Evaluation

One focused learning case mines the stable tool subsequence from successful traces while excluding failures and retaining only stable arguments. Nine trajectory cases cover the execution and cache boundaries around the learned procedure. This evaluates Mari's deterministic procedure representation, not Voyager or Reflexion task success.

```console
$ pytest -q tests/test_procedures.py tests/test_trajectories_agents.py
10 passed
```


Successful trajectories produce versioned procedure candidates. Regression gates and human review separate observed behavior from active behavior.

## How it works

Cluster successful traces by reviewed intent, extract a parameterized tool/action sequence with preconditions and failure exits, and retain links to the source traces. Replay the candidate on held-out cases, compare task success, tool correctness, grounding, cost, and regressions with the active version, then produce a review proposal. Only an explicit application commit can activate a version; failed attempts remain negative evidence.

**Research basis**[Voyager](https://arxiv.org/abs/2305.16291){.paper} stores compositional skills and improves them using execution feedback, errors, and self-verification. [Reflexion](https://arxiv.org/abs/2303.11366){.paper} retains verbal feedback for later trials. They motivate persistent procedural candidates; held-out regression gates and human promotion are conservative Mari policies, not conclusions of either paper.

:::{container} diagram lifecycle
trajectories*→*candidate*→*regression suite*→*review*→*active version
:::

```{code-block} python
:caption: Extract the stable tool subsequence across successful traces

from mari_components.trajectories import TrajectoryStep, learn_procedure

runs = {
    "run-1": [
        TrajectoryStep(0, "lookup_policy", "inspect", {"tier": "enterprise"}, ok=True),
        TrajectoryStep(1, "issue_refund", "execute", {"currency": "USD"}, ok=True),
    ],
    "run-2": [
        TrajectoryStep(0, "lookup_policy", "inspect", {"tier": "enterprise"}, ok=True),
        TrajectoryStep(1, "check_account", "inspect", ok=True),
        TrajectoryStep(2, "issue_refund", "execute", {"currency": "USD"}, ok=True),
    ],
}

candidate = learn_procedure(runs, intent="process enterprise refund")
assert [step.tool for step in candidate.steps] == [
    "lookup_policy",
    "issue_refund",
]
```
