[]{#procedures}[Proposed]{.proposed-label}

# Procedural knowledge

```{include} ../_includes/eval/agents.md
```

Successful trajectories could produce versioned procedure candidates. Regression gates and human review would separate observed behavior from active behavior.

## How it works

Cluster successful traces by reviewed intent, extract a parameterized tool/action sequence with preconditions and failure exits, and retain links to the source traces. Replay the candidate on held-out cases, compare task success, tool correctness, grounding, cost, and regressions with the active version, then produce a review proposal. Only an explicit application commit can activate a version; failed attempts remain negative evidence.

**Research basis**[Voyager](https://arxiv.org/abs/2305.16291){.paper} stores compositional skills and improves them using execution feedback, errors, and self-verification. [Reflexion](https://arxiv.org/abs/2303.11366){.paper} retains verbal feedback for later trials. They motivate persistent procedural candidates; held-out regression gates and human promotion are conservative Mari policies, not conclusions of either paper.

:::{container} diagram lifecycle
trajectories*→*candidate*→*regression suite*→*review*→*active version
:::

```{code-block} python
:caption: proposed / procedures.py

candidate = learn_procedure(successful_runs, intent="process enterprise refund")
report = evaluate_procedure(candidate, cases=refund_regression_suite,
    metrics=[TaskSuccess(), ToolCorrectness(), Groundedness(), Cost()])
if report.passes_gates:
    procedures.propose(candidate, report=report)  # review still required
```
