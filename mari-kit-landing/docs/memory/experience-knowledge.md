[]{#experience-knowledge}[Current]{.current-label}

# Knowledge from experience

Mari treats completed work as another changing knowledge source. A trajectory
is evidence: it records what information was available, what happened, and
where an expert corrected the result. The output is a reviewable fact,
strategy, constraint, pitfall, or bounded edit—not an agent loop or prescribed
workflow.

## At a glance

| Input | Mari operation | Output |
|---|---|---|
| Activity plus loaded artifact revisions | Diagnose expert feedback | Knowledge, procedure, ambiguity, or tool-execution finding |
| Successful, failed, and corrected activity | Extract and compare | Evidence-bound facts, strategies, pitfalls, and constraints |
| Existing documents plus accepted diagnoses | Propose a minimal change | Exact revision-bound edits for review |
| Caller-designed knowledge files | Inspect structure | Dependency, cycle, identity, and token-budget issues |

:::{collapse} Measured compatibility and known-answer checks

| Input | Cases | Observed result | What it establishes |
|---|---:|---:|---|
| PlugMem Apache-2.0 coding fixture | 3 sessions, 12 events | 2 tool results: 1 explicit success, 1 explicit failure | The adapter retains the fixture's outcome distinction |
| Contrastive fixture | 4 runs | `retry`: 0/2 successful, 2/2 failed; risk ratio `5.00` | Association direction and zero-cell correction are correct |
| Loaded-knowledge diagnosis | 1 correction | 1 accepted citation to 1 loaded revision | The diagnosis joins feedback to observed knowledge use |

The risk-ratio interval is wide (`0.38–66.01`) because four runs provide little
statistical certainty. Mari exposes that uncertainty instead of presenting
`5.00` alone as a conclusion.
:::

## Decide whether the knowledge was missing

| Correction and observed state | Diagnosis | Next knowledge operation |
|---|---|---|
| Correct fact was absent from loaded artifacts | Knowledge gap | Propose factual knowledge |
| Correct fact was loaded but applied incorrectly | Procedure gap | Propose a strategy or pitfall |
| Current artifacts disagree | Ambiguity | Surface the conflict for resolution |
| Correct knowledge was selected; the API failed | Tool execution | Preserve the failure; do not manufacture knowledge |

```{code-block} python
:caption: Bind a correction to the knowledge visible during the run

from mari_components.knowledge import (
    ExpertFeedback, KnowledgeUse, TrajectoryEvidence,
    build_knowledge_use_manifest, parse_feedback_diagnoses,
)

manifest = build_knowledge_use_manifest(
    run,
    [KnowledgeUse(
        artifact_id="plans", revision="r7",
        first_step=0, last_step=3,
        use="selected a plan limit",
    )],
)
feedback = ExpertFeedback(
    feedback_id="review-42",
    correction="Use the enterprise limit.",
    evidence=TrajectoryEvidence(
        trajectory_id=run.trajectory_id, start=2, end=3
    ),
)
diagnoses = parse_feedback_diagnoses(
    [run], [manifest], [feedback], model_output
)
```

The parser rejects unknown runs, out-of-range evidence, repeated feedback IDs,
and citations to artifacts that were not loaded. A `procedure_gap` must be
resolvable from loaded knowledge; a `knowledge_gap` must not be. The model
proposes the semantic judgment; Mari validates its observable claims.

::: source-block
**Evidence**

[Meta organizational second brain](https://engineering.fb.com/2026/09/02/ml-applications/organizational-second-brain-ai-learns-from-experts/){.paper}[ReasoningBank](https://research.google/blog/reasoningbank-enabling-agents-to-learn-from-experience/){.paper}[PlugMem](https://www.microsoft.com/en-us/research/blog/from-raw-interaction-to-reusable-knowledge-rethinking-memory-for-ai-agents/){.paper}
:::

## Extract reusable knowledge

`parse_experience_knowledge(runs, model_output)` accepts four neutral knowledge
kinds. It does not decide where they live or how they are composed.

| Kind | Candidate example | Limitation worth retaining |
|---|---|---|
| Fact | Enterprise limit is 20 seats | Effective date and account tier |
| Strategy | Resolve tier before selecting a limit | Only applies to tiered products |
| Pitfall | Do not infer tier from company size | Requires authoritative tier metadata |
| Constraint | Never expose restricted plan notes | Caller must still enforce ACLs |

```{code-block} python
:caption: Parse an evidence-bound candidate without accepting it

from mari_components.knowledge import parse_experience_knowledge

candidates = parse_experience_knowledge(
    [run],
    {"knowledge": [{
        "kind": "strategy",
        "title": "Resolve the plan before reading limits",
        "content": "Read the account plan, then select its matching limit.",
        "evidence": [{
            "trajectory_id": run.trajectory_id, "start": 0, "end": 3
        }],
        "applicability": ["tiered account limits"],
        "limitations": ["requires current account metadata"],
    }]},
)
assert candidates[0].evidence[0].end == 3
```

Candidate identity hashes kind, title, content, and exact evidence ranges.
Promotion remains a separate admission or mutation decision.
`mine_outcome_associations` finds contiguous activity patterns and reports
support in successful and failed runs, failure risk ratio, confidence interval,
and source run IDs. These are descriptive associations, not causal effects.

:::{collapse} Known-answer comparison used to verify the statistic

| Pattern | Successful support | Failed support | Interpretation |
|---|---:|---:|---|
| `search → answer` | 2 / 2 | 0 / 2 | Associated with successful examples |
| `retry` | 0 / 2 | 2 / 2 | Associated with failed examples; inspect those source runs |

The fixture verifies direction, zero-cell handling, and evidence IDs. It is not
an estimate of production risk.
:::

::: source-block
**Evidence**

[ReasoningBank paper](https://arxiv.org/abs/2509.25140){.paper}[PlugMem paper](https://arxiv.org/abs/2603.03296){.paper}[Haldane correction for zero cells](https://doi.org/10.2307/3001614){.paper}
:::

## Compare bounded episodes before extracting knowledge

Long activity histories need smaller evidence units. `parse_turn_assessments`
binds a model's situation, intent, action, progress, and outcome description to
non-overlapping source ranges. `segment_episodes` groups those turns at
caller-selected boundaries. `parse_episode_reflection` compares a focal
episode with named peers and returns applicability, hints, pitfalls, and
confidence; it does not promote the reflection to knowledge.

```{code-block} python
:caption: Keep segmentation separate from knowledge extraction

from mari_components.trajectories import (
    parse_episode_reflection, parse_turn_assessments, segment_episodes,
)

turns = parse_turn_assessments(run, turn_output)
episodes = segment_episodes(run, turns, boundaries=reviewed_episode_ends)
reflection = parse_episode_reflection(
    episodes[0], episodes[1:], reflection_output
)

# A separate parser may now propose a fact, strategy, pitfall, or constraint.
```

| Boundary | Owner | Validation |
|---|---|---|
| Turn ranges | Model proposes; Mari checks | In bounds, non-overlapping, exact evidence indices |
| Episode ends | Caller | In range, increasing, includes final turn |
| Comparison set | Model proposes; Mari checks | Existing peers only; focal episode excluded |
| Promotion | Caller | Reflection remains a candidate until separately admitted |

::: source-block
**Evidence**

[Amazon Bedrock episodic memory](https://aws.amazon.com/blogs/machine-learning/build-agents-to-learn-from-experiences-using-amazon-bedrock-agentcore-episodic-memory/){.paper}[PlugMem](https://arxiv.org/abs/2603.03296){.paper}
:::

## Propose and evaluate minimal changes

```{code-block} python
:caption: Validate an exact, revision-bound edit proposal

from mari_components.knowledge import parse_knowledge_change

proposal = parse_knowledge_change(
    {policy.document_id: policy},
    diagnoses,
    {
        "diagnosis_ids": ["review-42"],
        "edits": [{
            "document_id": policy.document_id,
            "original": "Enterprise limit is unspecified.",
            "replacement": "Enterprise limit is 20 seats.",
            "reason": "The expert correction resolves the missing value.",
        }],
        "affected_artifact_ids": ["plans", "support-routing"],
    },
)
```

The original text must occur exactly once, the replacement must differ, every
diagnosis must exist, and every edit carries the current source revision. Mari
returns a proposal; it never writes the document.

| Evaluation | Comparison | Decision information |
|---|---|---|
| Targeted replay | Corrected cases before and after | Did the proposed knowledge fix its stated problem? |
| Regression replay | Previously passing unrelated cases | What collateral behavior changed? |
| Blind review | Independently scored variants | Do reviewers prefer the content without knowing which is new? |
| Paired bootstrap | Same cases under both revisions | What is the mean delta and its uncertainty? |

`compare_paired_metrics` returns means, delta, bootstrap interval, and
wins/ties/losses. `summarize_repeated_trials` reports permutation-independent
pass@k and pass^k. `summarize_review_reliability` exposes agreement, expected
agreement, kappa, and duplicate reviewer submissions.

::: source-block
**Evidence**

[Meta on minimal edits, independent review, validation, and replay](https://engineering.fb.com/2026/09/02/ml-applications/organizational-second-brain-ai-learns-from-experts/){.paper}[Anthropic agent evaluations](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents){.paper}[Bootstrap confidence intervals](https://doi.org/10.1214/ss/1177013815){.paper}
:::

## Validate caller-designed knowledge structures

`inspect_knowledge_structure(files, maximum_tokens=None)` checks a structure;
it does not choose one.

| Check | Mechanism | Returned evidence |
|---|---|---|
| Stable identity | Count artifact IDs | Every duplicate |
| Dependency integrity | Resolve each `depends_on` target | Missing source and target IDs |
| Reverse dependencies | Compare `depends_on` with `referenced_by` | Every asymmetric pair |
| Cycles | Depth-first traversal over caller edges | Participating artifact IDs |
| Context density | Sum observed token counts | Total and optional budget issue |

```{code-block} python
:caption: Inspect a structure without prescribing its hierarchy

from mari_components.knowledge import KnowledgeFile, inspect_knowledge_structure

report = inspect_knowledge_structure([
    KnowledgeFile(
        artifact_id="plans", revision="r7", token_count=640,
        referenced_by=("support-routing",),
    ),
    KnowledgeFile(
        artifact_id="support-routing", revision="r3", token_count=410,
        depends_on=("plans",),
    ),
], maximum_tokens=2_000)

assert report.valid and report.total_tokens == 1_050
```

::: source-block
**Evidence**

[Meta on explicit dependencies and structural validation](https://engineering.fb.com/2026/09/02/ml-applications/organizational-second-brain-ai-learns-from-experts/){.paper}[W3C PROV data model](https://www.w3.org/TR/prov-dm/){.paper}
:::

## Normalize activity as evidence

`normalize_genai_trace` accepts OTLP JSON or flat spans, retains IDs,
parentage, timing, usage, links, and explicit status, and removes prompts,
messages, content, results, and arguments. `inspect_trace_integrity` reports
duplicate IDs, missing or cross-trace parents, cycles, negative durations, and
missing schema identity. `project_tool_trajectory` is the optional bridge to
Mari's compact activity values.

```{code-block} python
:caption: Inspect telemetry before using it as knowledge evidence

from mari_components.trajectories import (
    inspect_trace_integrity, normalize_genai_trace, project_tool_trajectory,
)

trace = normalize_genai_trace(otlp_export, maximum_events=20_000)
integrity = inspect_trace_integrity(trace)
if integrity.valid:
    run = project_tool_trajectory(trace, outcome="failure")
```

Unknown status remains `None`, distinct from success. Mari neither stores the
trace nor infers outcomes from text.

::: source-block
**Evidence**

[OpenTelemetry GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions-genai){.paper}[OpenTelemetry trace specification](https://opentelemetry.io/docs/specs/otel/trace/){.paper}
:::
