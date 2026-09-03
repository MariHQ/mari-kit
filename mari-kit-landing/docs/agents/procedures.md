[]{#procedures}[Current]{.current-label}

# Procedural knowledge

## Measured behavior

| Input evidence | Learned result |
|---|---|
| Repeated successful tool sequences | Stable longest common subsequence |
| Arguments identical at every occurrence | Retained arguments |
| Arguments vary between runs | Tool retained with arguments omitted |
| Failed trajectories | Kept as evaluation evidence and excluded from successful-path mining |

Across 60 AgentBench DB tasks, controlled successful traces recovered the
intended two-step sequence. The measurement covers the mining rule. Task
execution and uplift require an agent-level study.


:::{collapse} Mined procedure example

| Run | Tool sequence | Included in learned subsequence |
|---|---|---|
| Success A | `lookup_policy → issue_refund → notify` | First two stable steps |
| Success B | `lookup_policy → issue_refund` | Both steps |
| Failure | `issue_refund → error` | Excluded from positive subsequence |

Learned result: `lookup_policy → issue_refund`.
:::



Successful trajectories produce versioned procedure candidates. Regression
gates check their measured behavior. Human review controls activation.

## How it works

Start with successful traces grouped by a reviewed intent. `learn_procedure`
extracts a parameterized action sequence and retains source links. The caller
adds preconditions and failure exits as domain values. Replay evaluates the
candidate on held-out cases. Its report includes task success, grounding,
cost, tool correctness, and regressions against the active version. A review
proposal can then enter the application's commit path. Failed attempts stay
available as negative evidence.

**Research basis**[Voyager](https://arxiv.org/abs/2305.16291){.paper} stores
compositional skills and updates them from execution feedback. Its process also
uses errors and self-verification. [Reflexion](https://arxiv.org/abs/2303.11366){.paper}
retains verbal feedback for later trials. Persistent procedural candidates draw
on these mechanisms. Mari adds held-out regression gates and human promotion
as library policies.

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
non-empty and every step must have `ok is True`. Keep failed and unknown
outcomes in separate input records. The function computes a deterministic longest
common tool subsequence. Arguments are retained when every aligned occurrence
contains the same safe normalized values.

The result contains a content-derived procedure ID and revision, the source
trajectory IDs, and immutable `ProcedureStep` values. The returned value is a
candidate. Execution and promotion happen in application code.
