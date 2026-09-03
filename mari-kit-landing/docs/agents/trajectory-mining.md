[]{#trajectory-mining}[Current]{.current-label}

# Trajectory mining

## At a glance

| Evaluation | Input | Result | What it establishes |
|---|---:|---:|---|
| Public Plumbline corpus | 7 trajectories, 118 events | 8 activities, 6 exact variants | The process miner accepts a real, heterogeneous action log without a runtime adapter |
| Planted successful-path corpus | 13 known invariants | Precision `1.000`, recall `1.000` | Every planted call, order, ceiling, outcome, and absence rule was recovered |
| Path matching fixtures | 4 comparisons | `4/4` expected decisions | Strict, unordered, subsequence, and negative comparisons retain their intended semantics |
| Four-cluster vector fixture | 12 trajectories, 4 selected | `4/4` clusters represented | Greedy farthest-point selection does not spend the inspection budget on one dense neighborhood |
| Trace adapters | OpenAI, Anthropic, OTLP | `3/3` tool calls normalized | The three adapters preserve tool identity and explicit versus unknown outcomes |

The public corpus is deliberately rich in repeated adversarial actions, so its
measured rework rate (`0.695`) is a description of that corpus, not a target or
baseline for ordinary agents.
Use the known-answer rows to check algorithm semantics and the public-corpus
row to judge data-shape compatibility; neither predicts application quality.

:::{collapse} One process model, as data

| Run | Observed activities | Process result |
|---|---|---|
| A | `search → read → answer` | Variant A, three direct-follow edges |
| B | `search → read → answer` | Variant A support becomes two |
| C | `search → search → answer` | One sequential rework event |
| D | two `search` calls sharing one parent | Parallel batch; not counted as sequential rework |
:::

## Normalize trace exports

The adapters translate common export shapes into `TrajectoryStep`. They do not
retain tool-result bodies, call a model, infer task success from prose, or
write a trace store.

```{code-block} python
:caption: Preserve an unknown tool outcome instead of guessing

from mari_components.trajectories import normalize_openai_trajectory

result = normalize_openai_trajectory(messages, maximum_events=10_000)
step = result.steps[0]

assert step.tool == "search"
assert step.ok is None  # an ordinary tool message has no portable status
```

| Function | Input and options | Output |
|---|---|---|
| `normalize_openai_trajectory(records, *, maximum_events=10_000)` | Chat Completions messages or Responses API items | Steps, positioned adapter issues, dropped-record count |
| `normalize_anthropic_trajectory(messages, *, maximum_events=10_000)` | `tool_use` and `tool_result` blocks | Same result; `is_error` supplies an explicit outcome |
| `normalize_otel_trajectory(spans, *, maximum_events=10_000)` | OpenTelemetry GenAI attribute spellings | Time-ordered steps with IDs, parents, token counts, cost, and status when supplied |
| `normalize_steps(events, *, family_map=...)` | Mari's small `{name, args, summary, ok}` record | Privacy-bounded `TrajectoryStep` values |

Sensitive argument names are removed by `normalize_steps`. A missing outcome
remains `None`; procedure and success-invariant mining never treat it as a
successful call.

## Mine process structure

`canonicalize_activity` removes call arguments, generated numeric IDs, path
arguments, and retry suffixes. Resource names such as `chat:model-name` reduce
to the activity `chat`; the caller can retain the model separately.

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
| Exact variant | Complete canonical activity tuple; no edit-distance collapse |
| Sequential rework | A repeated activity within one run |
| Parallel event | Sibling steps with the same non-empty parent; excluded from sequential rework |
| Variant reuse | Fraction of runs belonging to a variant observed more than once |
| Cost and duration | Sums of caller-observed values; missing measurements contribute zero |

## Compare paths

```{code-block} python
:caption: Accept a shorter valid path while showing the omitted step

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
| `subsequence` | Every observed step appears in reference order; reference may contain extras |
| `supersequence` | Every reference step appears in observed order; observed may contain extras |

Every result also includes aligned index pairs, unmatched positions,
Levenshtein edit distance, and normalized similarity. Tool arguments are exact
by default; pass `matches=` to define domain-specific equivalence.

## Mine and check invariants

`mine_trajectory_invariants` considers only runs explicitly marked `success`.
It emits evidence-bearing candidates rather than tests, policies, or gates.

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
| `always_calls` | All successful runs; support names runs containing the tool |
| `never_calls` | Only tools in caller-supplied `available_tools`; absence cannot be learned from an unknown universe |
| `precedes` | Runs containing both tools; every occurrence of the first must precede every occurrence of the second |
| `max_calls` | Runs containing the tool; ceiling is the maximum observed successful count |
| `always_succeeds` | Runs containing the tool; unknown outcomes do not count as support |
| `argument_domain` | Opt-in argument names only; observed scalar values remain visible |

## Select trajectories for inspection

`select_diverse_trajectories(vectors, *, limit, relevance=None,
density=None, distance_exponent=1.0)` applies greedy farthest-point sampling in
the original normalized embedding space. The optional relevance and density
weights are supplied by the caller. The result retains each selection score,
minimum distance, rank, and every excluded ID.

::: source-block
**Research and implementations**

[Hodoscope: action abstraction and diverse trajectory inspection](https://github.com/AR-FORUM/hodoscope){.paper}[AgentEvals trajectory matching](https://github.com/langchain-ai/agentevals){.paper}[TraceRoutine process mining](https://github.com/gurov/traceroutine){.paper}[Trace-to-Evals invariant mining](https://github.com/a-bhimava/agent-trace-to-evals){.paper}[Plumbline intent-relative trajectory analysis](https://github.com/askalf/plumbline){.paper}[Process Mining: Data Science in Action](https://doi.org/10.1007/978-3-662-49851-4){.paper}

[Mari uses independent immutable values and pure functions. It does not include the reference dashboards, model clients, CI generation, enforcement, or trace storage.]{.small}
:::
