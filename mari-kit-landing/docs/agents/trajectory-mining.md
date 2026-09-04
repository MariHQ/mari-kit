[]{#trajectory-mining}[Research]{.current-label}

# Trajectory mining

## Measured behavior

| Evaluation | Input | Result | What it establishes |
|---|---:|---:|---|
| Public Plumbline corpus | 7 trajectories, 118 events | 8 activities, 6 exact variants | The process miner accepts a heterogeneous action log through its data API |
| Planted successful-path corpus | 13 known invariants | Precision `1.000`, recall `1.000` | Every planted call, order, ceiling, outcome, and absence rule was recovered |
| Path matching fixtures | 4 comparisons | `4/4` expected decisions | Strict, unordered, subsequence, and negative comparisons retain their intended semantics |
| Four-cluster vector fixture | 12 trajectories, 4 selected | `4/4` clusters represented | Greedy farthest-point selection covers every planted neighborhood |
| Trace adapters | OpenAI, Anthropic, OTLP | `3/3` tool calls normalized | The three adapters preserve tool identity and explicit versus unknown outcomes |

The public corpus contains many repeated adversarial actions. Its measured
rework rate of `0.695` describes that input. Known-answer rows check algorithm
semantics. The public-corpus row covers data-shape compatibility. Application
quality requires evaluation with the target agent and workload.

:::{collapse} Process model example

| Run | Observed activities | Process result |
|---|---|---|
| A | `search → read → answer` | Variant A, four edges including start and end |
| B | `search → read → answer` | Variant A support becomes two |
| C | `search → search → answer` | One sequential rework event |
| D | two `search` calls sharing one parent | Parallel batch, excluded from sequential rework |
:::

## Normalize trace exports

The adapters translate common export shapes into `TrajectoryStep`. Their output
keeps metadata selected by the schema. Tool-result bodies stay with the host.
Model calls and trace storage also remain application operations. Success
requires an explicit source field.

```{code-block} python
:caption: Preserve an unknown tool outcome

from mari_components.trajectories import normalize_openai_trajectory

result = normalize_openai_trajectory(messages, maximum_events=10_000)
step = result.steps[0]

assert step.tool == "search"
assert step.ok is None  # portable status unavailable
```

| Function | Input and options | Output |
|---|---|---|
| `normalize_openai_trajectory(records, *, maximum_events=10_000)` | Chat Completions messages or Responses API items | Steps, positioned adapter issues, dropped-record count |
| `normalize_anthropic_trajectory(messages, *, maximum_events=10_000)` | `tool_use` and `tool_result` blocks | Same result. `is_error` supplies an explicit outcome |
| `normalize_otel_trajectory(spans, *, maximum_events=10_000)` | OpenTelemetry GenAI attribute spellings | Time-ordered steps with IDs, parents, token counts, cost, and status when supplied |
| `normalize_steps(events, *, family_map=...)` | Mari's small `{name, args, summary, ok}` record | Privacy-bounded `TrajectoryStep` values |

Sensitive argument names are removed by `normalize_steps`. A missing outcome
remains `None`. Procedure mining and success-invariant mining require an
explicit successful outcome.

## Mine process structure

`canonicalize_activity` removes call arguments, generated numeric IDs, path
arguments, and retry suffixes. Resource names such as `chat:model-name` reduce
to the activity `chat`. The caller can retain the model separately.

```{code-block} python
:caption: Direct-follow edges, exact path variants, rework, and cost

from mari_components.trajectories import TrajectoryRun, mine_trajectory_process

process = mine_trajectory_process(
    [TrajectoryRun(trajectory_id="run-17", steps=result.steps)],
    activity_aliases={"vector_search": "retrieve"},
)

for edge in process.transitions:
    print(edge.source, edge.target, edge.occurrences, edge.parallel)
```

| Value | How it is computed |
|---|---|
| Direct-follow transition | Adjacent canonical activities, plus explicit start and end nodes |
| Exact variant | Complete canonical activity tuple with exact equality |
| Sequential rework | A repeated activity within one run |
| Parallel event | Sibling steps with the same non-empty parent. Excluded from sequential rework |
| Variant reuse | Fraction of runs belonging to a variant observed more than once |
| Cost and duration | Sums of caller-observed values. Missing measurements contribute zero |

## Compare paths

```{code-block} python
:caption: Compare a shorter observed path with its reference

from mari_components.trajectories import (
    TrajectoryMatchMode,
    compare_trajectories,
)

match = compare_trajectories(
    observed,
    reference,
    mode=TrajectoryMatchMode.SUBSEQUENCE,
    matches=lambda actual, expected: actual.tool == expected.tool,
)

assert match.matched
print(match.missing_reference_indices)
```

| Mode | Condition |
|---|---|
| `strict` | Same length and matching steps at every position |
| `unordered` | Same multiset under the supplied matcher |
| `subsequence` | Every observed step appears in reference order. Reference extras are allowed |
| `supersequence` | Every reference step appears in observed order. Observed extras are allowed |

Every result includes aligned index pairs and unmatched positions. It also
reports Levenshtein edit distance with normalized similarity. Tool arguments
use exact equality by default. Pass `matches=` to define domain-specific
equivalence.

## Mine and check invariants

`mine_trajectory_invariants` requires runs explicitly marked `success`.
It emits evidence-bearing candidates. Callers can turn reviewed candidates
into tests, policies, or gates.

```{code-block} python
:caption: Inspect learned regularities before deciding whether to enforce them

from mari_components.trajectories import (
    check_trajectory_invariant,
    mine_trajectory_invariants,
)

candidates = mine_trajectory_invariants(
    historical_runs,
    available_tools={"search", "read", "answer", "delete"},
    argument_names={"scope"},
    minimum_support=0.95,
    minimum_applicable=20,
)

violations = [
    violation
    for candidate in candidates
    if (violation := check_trajectory_invariant(candidate, new_run)) is not None
]
```

| Candidate kind | Applicability and evidence |
|---|---|
| `always_calls` | All successful runs. Support names runs containing the tool |
| `never_calls` | Tools in caller-supplied `available_tools`. The declared universe defines absence |
| `precedes` | Runs containing the paired tools. Every occurrence of the first must precede every occurrence of the second |
| `max_calls` | Runs containing the tool. Ceiling is the maximum observed successful count |
| `always_succeeds` | Runs containing the tool. Support requires explicit successful outcomes |
| `argument_domain` | Caller-selected argument names. Observed scalar values remain visible |

## Select trajectories for inspection

`select_diverse_trajectories(vectors, *, limit, relevance=None,
density=None, distance_exponent=1.0)` applies greedy farthest-point sampling in
the original normalized embedding space. The optional relevance and density
weights are supplied by the caller. The result retains each selection score,
minimum distance, rank, and every excluded ID.

Sampling weights multiply relevance, density, and distance. Equal scores break
ties by trajectory ID. Keep the embedding model and weight recipe fixed across
comparisons, and include rare failure cases explicitly in the review set.
Feed selected observations into [conversation knowledge](conversation-knowledge.md)
for searchable lessons, or successful traces into [procedure mining](procedures.md).

::: source-block
**Research and implementations**

[Hodoscope: action abstraction and diverse trajectory inspection](https://github.com/AR-FORUM/hodoscope){.paper}[AgentEvals trajectory matching](https://github.com/langchain-ai/agentevals){.paper}[TraceRoutine process mining](https://github.com/gurov/traceroutine){.paper}[Trace-to-Evals invariant mining](https://github.com/a-bhimava/agent-trace-to-evals){.paper}[Plumbline intent-relative trajectory analysis](https://github.com/askalf/plumbline){.paper}[Process Mining: Data Science in Action](https://doi.org/10.1007/978-3-662-49851-4){.paper}

[Mari uses independent immutable values and pure functions. Applications supply
dashboards and model clients. CI generation, enforcement, and trace storage
connect through the returned records.]{.small}
:::
