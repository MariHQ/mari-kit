[]{#trajectories}[Research]{.current-label}

# Trajectories and agent evaluation

## Recorded behavior

| Input | Stored form | Safety boundary |
|---|---|---|
| Tool event | Ordered normalized step | Sensitive argument names and payloads are removed |
| OpenAI, Anthropic, or OTLP export | Adapter result with issues | Missing status remains unknown |
| Failed call | Negative outcome | Failure remains available for later evaluation |
| Model-proposed phases | Validated ranges | Every step must be covered exactly once |

The included trace study uses 60 AgentBench-shaped database interactions. It
measures normalization and ordering. Live task success needs an evaluation in
the target environment.


:::{collapse} Normalized trace example

| Runtime event | Stored trajectory step |
|---|---|
| Tool call with token and query | Tool name retained. Sensitive arguments redacted |
| Failed tool result | Failure outcome retained |
| Model phase covering steps `2–4` | Accepted when phases cover every step once |
| Speculative read | Recorded as a real asynchronous task |
:::



`normalize_steps` converts runtime records into privacy-bounded
`TrajectoryStep` values. `parse_trajectory_analysis` validates phases proposed
by a model. Export adapters feed the same representation. The application
supplies its agent loop.

## How it works

Adapters map framework events into ordered `AgentEvent` values. Normalization
assigns each step a stable position. It keeps allowlisted metadata. Sensitive
argument names and transport fields are redacted. Tool evaluation
compares observed calls with expected names and counts. Outcome evaluation
checks terminal paths and completion. A proposed phase analysis must cover
every observed event once. Its ranges must be contiguous and disjoint, with a
known family for each tool.

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

`AgentEvent` and `EventKind` are framework-neutral. Optional adapters cover OpenAI Agents and LangChain/LangGraph. Normalization redacts common sensitive arguments. Phase validation requires the returned ranges to cover observed events exactly.

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
| `normalize_steps(events, *, family_map=DEFAULT_FAMILY_MAP)` | Replace the tool-to-family mapping. Unknown tools become `other` | Ordered steps with safe scalar arguments, outcome, IDs, parent, time, tokens, and cost |
| `normalize_openai_trajectory(records, *, maximum_events=10_000)` | Bounded Chat Completions or Responses input | Adapter issues plus normalized tool calls |
| `normalize_anthropic_trajectory(messages, *, maximum_events=10_000)` | Bounded `tool_use`/`tool_result` input | Explicit `is_error` outcomes are preserved |
| `normalize_otel_trajectory(spans, *, maximum_events=10_000)` | OpenTelemetry GenAI attribute aliases | Time-ordered tool spans |
| `parse_trajectory_analysis(events, model_output, *, family_map=...)` | Caller-supplied phase labels | Contiguous phases covering every normalized step exactly once |

An absent status maps to `None`. Mining functions require an explicit success
value, so unknown telemetry stays outside successful-run evidence.

::: source-block
**Research and standards**

[AgentBench: multi-environment agent evaluation](https://arxiv.org/abs/2308.03688){.paper}[OpenTelemetry trace specification](https://opentelemetry.io/docs/specs/otel/trace/){.paper}[Hodoscope multi-format trajectory analysis](https://github.com/AR-FORUM/hodoscope){.paper}[Rogrep multi-runtime session parsing](https://github.com/agentpmhq/rogrep){.paper}

[Mari's event schema, redaction list, exact phase coverage, and outcome predicates are library contracts.]{.small}
:::
