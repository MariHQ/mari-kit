[]{#trajectories}[Current]{.current-label}

# Trajectories and agent evaluation

## Evaluation

Nine trajectory cases cover portable framework events, redaction, exact phase coverage, tool and outcome failures, reviewed-cache selection, stale and unauthorized dependencies, and asynchronous speculative retrieval. These evaluate Mari's AgentBench/OpenTelemetry-facing adapter contract; no AgentBench environment success score is claimed.

```console
$ pytest -q tests/test_trajectories_agents.py
9 passed
```


`normalize_steps` converts runtime records into privacy-bounded `TrajectoryStep` values. `parse_trajectory_analysis` validates model-proposed phases. Mari provides adapters, not an agent loop.

## How it works

Adapters map framework events into ordered `AgentEvent` values. Normalization assigns stable step positions, keeps allowlisted metadata, and redacts sensitive argument names and transport fields. Tool evaluation compares observed names and counts against expectations; outcome evaluation compares terminal paths and completion. A proposed phase analysis must cover every observed event exactly once with contiguous, non-overlapping ranges and known tool families.

::::::{container} diagram timeline
<div>

**inspect**[search_knowledge]{.small}

</div>

<div>

**reason**[2 docs · 2 citations]{.small}

</div>

<div>

**answer**[outcome: resolved]{.small}

</div>
::::::

```{code-block} python
:caption: agents.py

from mari_components.agents import evaluate_outcome, evaluate_tools
from mari_components.trajectories import normalize_steps

steps = normalize_steps(runtime_events)
tools = evaluate_tools(events, expected_tools=("search_knowledge",))
outcome = evaluate_outcome(paths=("resolved",),
    expected_paths=("resolved",), completed=True)
```

`AgentEvent` and `EventKind` are framework-neutral. Optional adapters cover OpenAI Agents and LangChain/LangGraph. Normalization redacts common sensitive arguments; phase validation requires the returned ranges to cover observed events exactly.

```{code-block} python
:caption: trajectory_analysis.py

from mari_components.trajectories import parse_trajectory_analysis

analysis = parse_trajectory_analysis(normalized_events, model_labels,
    family_map={"search_product_knowledge": "inspect",
                "answer": "answer"})
```

::: source-block
**Research and standards**

[AgentBench: multi-environment agent evaluation](https://arxiv.org/abs/2308.03688){.paper}[OpenTelemetry trace specification](https://opentelemetry.io/docs/specs/otel/trace/){.paper}

[Mari's event schema, redaction list, exact phase coverage, and outcome predicates are library contracts.]{.small}
:::
