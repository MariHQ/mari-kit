[]{#trajectories}[Current]{.current-label}

# Trajectories and agent evaluation

## At a glance

| Input | Stored form | Safety boundary |
|---|---|---|
| Tool event | Ordered normalized step | Sensitive argument names and payloads are removed |
| OpenAI, Anthropic, or OTLP export | Adapter result with issues | Missing status remains unknown |
| Failed call | Negative outcome | Failure remains available for later evaluation |
| Model-proposed phases | Validated ranges | Every step must be covered exactly once |

The included trace study uses 60 AgentBench-shaped database interactions. It examines normalization and ordering, not live-environment task success.


:::{collapse} Worked normalized trace

| Runtime event | Stored trajectory step |
|---|---|
| Tool call with token and query | Tool name retained; sensitive arguments redacted |
| Failed tool result | Failure outcome retained |
| Model phase covering steps `2–4` | Accepted only if phases cover every step once |
| Speculative read | Recorded as a real asynchronous task |
:::



`normalize_steps` converts runtime records into privacy-bounded `TrajectoryStep` values. `parse_trajectory_analysis` validates model-proposed phases. Common export adapters feed the same representation. Mari provides adapters and algorithms, not an agent loop.

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

## Function definitions and options

| Function | Important options | Result |
|---|---|---|
| `normalize_steps(events, *, family_map=DEFAULT_FAMILY_MAP)` | Replace the tool-to-family mapping; unknown tools become `other` | Ordered steps with safe scalar arguments, outcome, IDs, parent, time, tokens, and cost |
| `normalize_openai_trajectory(records, *, maximum_events=10_000)` | Bounded Chat Completions or Responses input | Adapter issues plus normalized tool calls |
| `normalize_anthropic_trajectory(messages, *, maximum_events=10_000)` | Bounded `tool_use`/`tool_result` input | Explicit `is_error` outcomes are preserved |
| `normalize_otel_trajectory(spans, *, maximum_events=10_000)` | OpenTelemetry GenAI attribute aliases | Time-ordered tool spans |
| `parse_trajectory_analysis(events, model_output, *, family_map=...)` | Caller-supplied phase labels | Contiguous phases covering every normalized step exactly once |

An absent status is `None`, not `False`. This prevents unknown telemetry from
becoming negative training data or supporting a success invariant.

::: source-block
**Research and standards**

[AgentBench: multi-environment agent evaluation](https://arxiv.org/abs/2308.03688){.paper}[OpenTelemetry trace specification](https://opentelemetry.io/docs/specs/otel/trace/){.paper}[Hodoscope multi-format trajectory analysis](https://github.com/AR-FORUM/hodoscope){.paper}[Rogrep multi-runtime session parsing](https://github.com/agentpmhq/rogrep){.paper}

[Mari's event schema, redaction list, exact phase coverage, and outcome predicates are library contracts.]{.small}
:::
