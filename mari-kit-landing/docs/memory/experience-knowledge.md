[]{#experience-knowledge}[Reference]{.current-label}

# Knowledge from experience

Mari treats completed work as another changing knowledge source. A trajectory
is evidence: it records what information was available, what happened, and
where an expert corrected the result. The output is a reviewable fact,
strategy, constraint, pitfall, or bounded edit. It records evidence for review
and leaves workflow design to the application.

## Behavior

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
| Contrastive fixture | 4 runs | `retry`: 0/2 successful, 2/2 failed. Risk ratio `5.00` | Association direction and zero-cell correction are correct |
| Loaded-knowledge diagnosis | 1 correction | 1 accepted citation to 1 loaded revision | The diagnosis joins feedback to observed knowledge use |
| Observation ledger | Retrieved + cited, with use unobserved | Cited `1`. Used `0` | Each stage requires its own record |
| Derivation audit | Derived summary claimed independent | `1/1` detected | Generated material cannot masquerade as a new source |
| Coordinated edit | 2 exact edits in one document | Expected preview and 2 inverses | Edits compose against one immutable revision |

The risk-ratio interval is wide (`0.38–66.01`) because four runs provide little
statistical certainty. Mari exposes that uncertainty and reports the interval
alongside the observed ratio.
:::

## Decide whether the knowledge was missing

| Correction and observed state | Diagnosis | Next knowledge operation |
|---|---|---|
| Correct fact was absent from loaded artifacts | Knowledge gap | Propose factual knowledge |
| Correct fact was loaded and applied incorrectly | Procedure gap | Propose a strategy or pitfall |
| Current artifacts disagree | Ambiguity | Surface the conflict for resolution |
| Correct knowledge was selected and the API failed | Tool execution | Preserve the failure and leave the knowledge set unchanged |

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
and citations to artifacts outside the loaded set. A `procedure_gap` must be
resolvable from loaded knowledge. A `knowledge_gap` must remain unresolved. The model
proposes the semantic judgment. Mari validates its observable claims.

::: source-block
**Evidence**

[Meta organizational second brain](https://engineering.fb.com/2026/09/02/ml-applications/organizational-second-brain-ai-learns-from-experts/){.paper}[ReasoningBank](https://research.google/blog/reasoningbank-enabling-agents-to-learn-from-experience/){.paper}[PlugMem](https://www.microsoft.com/en-us/research/blog/from-raw-interaction-to-reusable-knowledge-rethinking-memory-for-ai-agents/){.paper}
:::

## Record observed knowledge stages

Retrieval, presentation, citation, and use are separate observations. A
retriever hits record retrieval. A separate use event records entry into model
context. Citations record provenance. A separate observation records influence
on the result.

| Recorded stage | Meaning | Separate measurement |
|---|---|---|
| `RETRIEVED` | An artifact revision was returned by retrieval | It was shown |
| `SHOWN` | The revision entered the supplied context | It was read or used |
| `CITED` | Output explicitly referenced the revision | The claim depended on it |
| `USED` | The host observed a defined use signal | Causal benefit requires an ablation |

```{code-block} python
:caption: Preserve the difference between retrieval and demonstrated use

from mari_components.knowledge import (
    KnowledgeObservation, KnowledgeObservationStage,
    inspect_knowledge_observations,
)

report = inspect_knowledge_observations([
    KnowledgeObservation(
        observation_id="obs-1", activity_id="answer-42",
        artifact_id="plans", revision="r7",
        stage=KnowledgeObservationStage.RETRIEVED, ordinal=0,
    ),
    KnowledgeObservation(
        observation_id="obs-2", activity_id="answer-42",
        artifact_id="plans", revision="r7",
        stage=KnowledgeObservationStage.SHOWN, ordinal=1,
    ),
])

assert report.retrieved == (("plans", "r7"),)
assert report.used == ()
```

The inspector detects duplicate observation IDs, a later event recorded before
an earlier stage, and a non-retrieval stage missing a preceding observation for
that activity and revision.

::: source-block
**Evidence**

[W3C PROV activities, entities, and derivations](https://www.w3.org/TR/prov-dm/){.paper}[Letta context hierarchy and observed memory](https://github.com/letta-ai/letta-code){.paper}[PlugMem context-relative utility](https://arxiv.org/abs/2603.03296){.paper}
:::

## Extract reusable knowledge

`parse_experience_knowledge(runs, model_output)` accepts four neutral knowledge
kinds. It leaves storage and composition to the caller.

| Kind | Candidate example | Limitation worth retaining |
|---|---|---|
| Fact | Enterprise limit is 20 seats | Effective date and account tier |
| Strategy | Resolve tier before selecting a limit | Applies to tiered products |
| Pitfall | Company size provides insufficient evidence for tier | Requires authoritative tier metadata |
| Constraint | Hide restricted plan notes | Caller enforces ACLs |

```{code-block} python
:caption: Parse an evidence-bound candidate for review

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
and source run IDs. These are descriptive associations.

:::{collapse} Known-answer comparison used to verify the statistic

| Pattern | Successful support | Failed support | Interpretation |
|---|---:|---:|---|
| `search → answer` | 2 / 2 | 0 / 2 | Associated with successful examples |
| `retry` | 0 / 2 | 2 / 2 | Associated with failed examples. Inspect those source runs |

The fixture verifies direction, zero-cell handling, and evidence IDs. Production
risk requires a separate estimate.
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
confidence. It returns the reflection for a later knowledge decision.

```{code-block} python
:caption: Record segmentation and knowledge extraction independently

from mari_components.trajectories import (
    parse_episode_reflection, parse_turn_assessments, segment_episodes,
)

turns = parse_turn_assessments(run, turn_output)
episodes = segment_episodes(run, turns, boundaries=reviewed_episode_ends)
reflection = parse_episode_reflection(
    episodes[0], episodes[1:], reflection_output
)

# A separate parser now proposes a fact, strategy, pitfall, or constraint.
```

| Boundary | Owner | Validation |
|---|---|---|
| Turn ranges | Model proposes. Mari checks | In bounds, non-overlapping, exact evidence indices |
| Episode ends | Caller | In range, increasing, includes final turn |
| Comparison set | Model proposes. Mari checks | Existing peer IDs, excluding the focal episode |
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
returns a proposal for the caller to write.

| Evaluation | Comparison | Decision information |
|---|---|---|
| Targeted replay | Corrected cases before and after | Did the proposed knowledge fix its stated problem? |
| Regression replay | Previously passing unrelated cases | What collateral behavior changed? |
| Blind review | Independently scored variants | Which content do reviewers prefer when version labels are hidden? |
| Paired bootstrap | Same cases under both revisions | What is the mean delta and its uncertainty? |

`compare_paired_metrics` returns means, delta, bootstrap interval, and
wins/ties/losses. `summarize_repeated_trials` reports permutation-independent
pass@k and pass^k. `summarize_review_reliability` exposes agreement, expected
agreement, kappa, and duplicate reviewer submissions.

::: source-block
**Evidence**

[Meta on minimal edits, independent review, validation, and replay](https://engineering.fb.com/2026/09/02/ml-applications/organizational-second-brain-ai-learns-from-experts/){.paper}[Anthropic agent evaluations](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents){.paper}[Bootstrap confidence intervals](https://doi.org/10.1214/ss/1177013815){.paper}
:::

## Validate a multi-document changeset

`validate_knowledge_changeset(documents, edits)` lifts exact edits into one
review unit. It checks every source revision and original substring, rejects
overlapping changes, builds complete previews, hashes proposed revisions, and
returns inverse edits. The caller applies them and defines any cross-store
transaction boundary.

```{code-block} python
:caption: Preview a coordinated correction across two artifacts

from mari_components.knowledge import (
    KnowledgeEdit, validate_knowledge_changeset,
)

changeset = validate_knowledge_changeset(
    {limits.document_id: limits, routing.document_id: routing},
    [
        KnowledgeEdit(
            document_id=limits.document_id, source_revision=limits.revision,
            original="Limit is 10", replacement="Limit is 20",
            reason="Correct enterprise limit",
        ),
        KnowledgeEdit(
            document_id=routing.document_id, source_revision=routing.revision,
            original="basic queue", replacement="enterprise queue",
            reason="Keep routing consistent",
        ),
    ],
)

for entry in changeset.entries:
    review(entry.preview, entry.inverse_edits)
```

| Failure | Validation reason |
|---|---|
| Unknown document | Target cannot be resolved |
| Revision mismatch | Edit was prepared against stale material |
| Original is absent or repeated | Replacement location is ambiguous |
| Edits overlap | Order would change their meaning |

::: source-block
**Evidence**

[JSON Patch](https://www.rfc-editor.org/rfc/rfc6902){.paper}[HTTP conditional requests and lost-update prevention](https://www.rfc-editor.org/rfc/rfc9110.html#name-conditional-requests){.paper}[Meta on minimal edits and deterministic validation](https://engineering.fb.com/2026/09/02/ml-applications/organizational-second-brain-ai-learns-from-experts/){.paper}
:::

## Validate caller-designed knowledge structures

`inspect_knowledge_structure(files, maximum_tokens=None)` checks a structure.
The report returns available choices for caller selection.

| Check | Mechanism | Returned evidence |
|---|---|---|
| Stable identity | Count artifact IDs | Every duplicate |
| Dependency integrity | Resolve each `depends_on` target | Missing source and target IDs |
| Reverse dependencies | Compare `depends_on` with `referenced_by` | Every asymmetric pair |
| Cycles | Depth-first traversal over caller edges | Participating artifact IDs |
| Context density | Sum observed token counts | Total and optional budget issue |

```{code-block} python
:caption: Inspect a caller-defined file hierarchy

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

## Detect derivation feedback loops

Generated summaries and facts can supply evidence. Their origin remains
derived material. `inspect_knowledge_derivations` checks immutable revision
references, missing inputs, derivation cycles, and any derived input labeled
`claimed_independent=True`.

```{code-block} python
:caption: Keep a generated summary linked to its source

from mari_components.knowledge import (
    DerivationInput, KnowledgeDerivation, KnowledgeOrigin,
    inspect_knowledge_derivations,
)

report = inspect_knowledge_derivations([
    KnowledgeDerivation(output=source_ref, origin=KnowledgeOrigin.SOURCE),
    KnowledgeDerivation(
        output=summary_ref,
        origin=KnowledgeOrigin.DERIVED,
        inputs=(DerivationInput(ref=source_ref),),
    ),
    KnowledgeDerivation(
        output=new_fact_ref,
        origin=KnowledgeOrigin.DERIVED,
        inputs=(DerivationInput(
            ref=summary_ref,
            claimed_independent=False,
        ),),
    ),
])
```

The check permits derived material and prevents a caller from
counting that material as independent corroboration and makes cyclic ancestry
visible before admission or aggregation.

::: source-block
**Evidence**

[W3C PROV derivation](https://www.w3.org/TR/prov-dm/#term-Derivation){.paper}[Nanopublication provenance](https://arxiv.org/abs/1809.06532){.paper}[The Curse of Recursion](https://arxiv.org/abs/2305.17493){.paper}
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

Unknown status remains `None`. Success requires an explicit positive value.
Mari stores the trace. Outcome inference from text belongs in a caller adapter.

::: source-block
**Evidence**

[OpenTelemetry GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions-genai){.paper}[OpenTelemetry trace specification](https://opentelemetry.io/docs/specs/otel/trace/){.paper}
:::
