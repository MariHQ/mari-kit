[]{#procedures}[Current]{.current-label}

# Procedural knowledge

## At a glance

| Input evidence | Learned result |
|---|---|
| Repeated successful tool sequences | Stable longest common subsequence |
| Arguments identical at every occurrence | Retained arguments |
| Arguments vary between runs | Tool retained with arguments omitted |
| Failed trajectories | Kept as evaluation evidence, not mined as success |

Across 60 AgentBench DB tasks, controlled successful traces recovered the intended two-step sequence. This validates the mining rule, not task execution or uplift.


:::{collapse} Worked mined procedure

| Run | Tool sequence | Included in learned subsequence |
|---|---|---|
| Success A | `lookup_policy → issue_refund → notify` | First two stable steps |
| Success B | `lookup_policy → issue_refund` | Both steps |
| Failure | `issue_refund → error` | Excluded from positive subsequence |

Learned result: `lookup_policy → issue_refund`.
:::



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

## Function definition and options

`learn_procedure(trajectories, *, intent)` accepts a mapping from caller-owned
trajectory IDs to ordered `TrajectoryStep` sequences. Every input run must be
non-empty and every step must have `ok is True`; failed and unknown outcomes
must be retained separately. The function computes a deterministic longest
common tool subsequence. Arguments survive only when every aligned occurrence
contains the same safe normalized values.

The result contains a content-derived procedure ID and revision, the source
trajectory IDs, and immutable `ProcedureStep` values. It is a candidate—not an
executable workflow or promotion decision.
