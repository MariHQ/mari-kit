# Complete module and API index

This source-derived index covers **167 public implementation modules**, **988 top-level class/function definitions**, and **188 public method declarations**. It includes algorithms, supporting records, protocols, adapters, and validators. These counts describe definitions rather than independent algorithms.

The [algorithm choices guide](https://kit.mari.guru/start/algorithm-choices.html) compares workloads and tradeoffs. Use this index to locate every public implementation family and inspect exact source definitions. Imported aliases, constants, private helpers, and dunder methods are outside the definition counts. Package facades appear separately below.

Source reference: [Mari Kit at d6f70a0](https://github.com/MariHQ/mari-kit/tree/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components). Each declaration links to its implementation. Research citations and adaptation boundaries appear in the algorithm guide and feature pages.

## Areas

- [Agent activity and experience](#agent-activity-and-experience)
- [Agent events and evaluation](#agent-events-and-evaluation)
- [Conformance utilities](#conformance-utilities)
- [Conversations and topics](#conversations-and-topics)
- [Documents and source structure](#documents-and-source-structure)
- [Evaluation and statistics](#evaluation-and-statistics)
- [Governance policies](#governance-policies)
- [Graph algorithms and interchange](#graph-algorithms-and-interchange)
- [Incremental maintenance](#incremental-maintenance)
- [Knowledge and memory](#knowledge-and-memory)
- [Platform composition and reference storage](#platform-composition-and-reference-storage)
- [Retrieval and context](#retrieval-and-context)
- [Selectable algorithm additions](#selectable-algorithm-additions)
- [Shared values and contracts](#shared-values-and-contracts)
- [Source connectors and event handling](#source-connectors-and-event-handling)
- [Source synchronization](#source-synchronization)
- [Verification and evidence decisions](#verification-and-evidence-decisions)

## Agent activity and experience

### mari_components.trajectories.adapters

Small adapters from common trace exports into normalized trajectory steps.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/adapters.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [TrajectoryAdapterIssue](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/adapters.py#L14) | class | — |
| [TrajectoryAdapterResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/adapters.py#L21) | class | — |
| [normalize_openai_trajectory](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/adapters.py#L66) | function | — |
| [normalize_anthropic_trajectory](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/adapters.py#L141) | function | — |
| [normalize_otel_trajectory](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/adapters.py#L195) | function | — |

### mari_components.trajectories.episodes

Evidence-bound turn, episode, and cross-episode reflection values.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/episodes.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [AssessmentStatus](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/episodes.py#L18) | class | — |
| [TurnAssessment](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/episodes.py#L26) | class | — |
| [Episode](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/episodes.py#L40) | class | — |
| [EpisodeReflection](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/episodes.py#L55) | class | — |
| [parse_turn_assessments](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/episodes.py#L65) | function | — |
| [segment_episodes](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/episodes.py#L110) | function | — |
| [parse_episode_reflection](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/episodes.py#L165) | function | — |

### mari_components.trajectories.experience

Contrastive trajectory associations and evidence-bound reasoning memories.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/experience.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [OutcomeAssociation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/experience.py#L22) | class | [support](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/experience.py#L34) |
| [mine_outcome_associations](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/experience.py#L38) | function | — |
| [ReasoningMemoryKind](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/experience.py#L108) | class | — |
| [ReasoningMemoryCandidate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/experience.py#L115) | class | — |
| [ReasoningMemoryComparison](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/experience.py#L128) | class | — |
| [parse_reasoning_memories](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/experience.py#L135) | function | — |
| [compare_reasoning_memories](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/experience.py#L201) | function | — |

### mari_components.trajectories.intent_analysis

Caller-embedded intent clustering, novelty detection, and temporal drift.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/intent_analysis.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [IntentCluster](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/intent_analysis.py#L15) | class | [support](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/intent_analysis.py#L24) |
| [IntentClustering](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/intent_analysis.py#L29) | class | — |
| [NovelIntent](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/intent_analysis.py#L35) | class | — |
| [IntentClusterChange](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/intent_analysis.py#L43) | class | — |
| [IntentDriftReport](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/intent_analysis.py#L52) | class | — |
| [cluster_intents](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/intent_analysis.py#L61) | function | — |
| [detect_novel_intents](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/intent_analysis.py#L139) | function | — |
| [compare_intent_windows](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/intent_analysis.py#L174) | function | — |

### mari_components.trajectories.intents

Evidence-bound intent proposals and corpus-level intent aggregation.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/intents.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [IntentKind](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/intents.py#L20) | class | — |
| [normalize_intent](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/intents.py#L26) | function | — |
| [IntentEvidence](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/intents.py#L34) | class | — |
| [IntentCandidate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/intents.py#L47) | class | — |
| [IntentAggregate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/intents.py#L70) | class | [support](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/intents.py#L78) |
| [IntentReview](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/intents.py#L83) | class | — |
| [IntentReviewSummary](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/intents.py#L90) | class | [agreement](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/intents.py#L98) |
| [parse_intent_candidates](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/intents.py#L103) | function | — |
| [aggregate_intents](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/intents.py#L193) | function | — |
| [summarize_intent_reviews](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/intents.py#L220) | function | — |

### mari_components.trajectories.invariants

Evidence-bearing invariant mining from successful agent trajectories.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/invariants.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [TrajectoryInvariantKind](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/invariants.py#L15) | class | — |
| [TrajectoryInvariant](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/invariants.py#L25) | class | [support_ratio](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/invariants.py#L39) |
| [TrajectoryInvariantViolation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/invariants.py#L44) | class | — |
| [mine_trajectory_invariants](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/invariants.py#L102) | function | — |
| [check_trajectory_invariant](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/invariants.py#L238) | function | — |

### mari_components.trajectories.matching

Reference-trajectory comparison without framework message types.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/matching.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [TrajectoryMatchMode](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/matching.py#L13) | class | — |
| [TrajectoryMatch](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/matching.py#L24) | class | — |
| [trajectory_edit_distance](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/matching.py#L38) | function | — |
| [compare_trajectories](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/matching.py#L61) | function | — |
| [tool_histogram](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/matching.py#L135) | function | — |

### mari_components.trajectories.mine

Grounded trajectory analysis using one caller-supplied model invocation.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/mine.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [TrajectoryPhase](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/mine.py#L17) | class | [steps](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/mine.py#L26) |
| [TrajectoryAnalysis](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/mine.py#L31) | class | — |
| [parse_trajectory_analysis](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/mine.py#L49) | function | — |

### mari_components.trajectories.normalize

Privacy-bounded normalization of observable tool telemetry.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/normalize.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [TrajectoryStep](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/normalize.py#L37) | class | [duration](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/normalize.py#L56), [tokens](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/normalize.py#L62) |
| [normalize_steps](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/normalize.py#L82) | function | — |

### mari_components.trajectories.procedures

Versioned procedural candidates learned from successful tool traces.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/procedures.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [ProcedureStep](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/procedures.py#L15) | class | — |
| [ProcedureCandidate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/procedures.py#L28) | class | — |
| [learn_procedure](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/procedures.py#L50) | function | — |

### mari_components.trajectories.process

Deterministic process-mining summaries over caller-owned trajectories.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/process.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [canonicalize_activity](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/process.py#L21) | function | — |
| [TrajectoryRun](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/process.py#L43) | class | — |
| [ActivityStatistics](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/process.py#L57) | class | — |
| [TransitionStatistics](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/process.py#L68) | class | — |
| [TrajectoryVariant](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/process.py#L78) | class | [occurrences](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/process.py#L85) |
| [TrajectoryProcess](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/process.py#L97) | class | [rework_rate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/process.py#L112), [variant_reuse](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/process.py#L116) |
| [mine_trajectory_process](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/process.py#L125) | function | — |

### mari_components.trajectories.rubrics

Task-adaptive rubric values and confidence-visible trajectory scoring.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/rubrics.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [RubricDimension](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/rubrics.py#L18) | class | — |
| [TrajectoryRubric](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/rubrics.py#L32) | class | — |
| [RubricAssessment](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/rubrics.py#L45) | class | — |
| [RubricScore](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/rubrics.py#L55) | class | — |
| [parse_trajectory_rubric](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/rubrics.py#L74) | function | — |
| [parse_rubric_assessments](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/rubrics.py#L103) | function | — |
| [score_trajectory_rubric](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/rubrics.py#L151) | function | — |

### mari_components.trajectories.sampling

Diversity-aware sampling for inspecting large trajectory corpora.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/sampling.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [TrajectorySample](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/sampling.py#L12) | class | — |
| [TrajectorySamplingResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/sampling.py#L22) | class | — |
| [select_diverse_trajectories](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/sampling.py#L27) | function | — |

### mari_components.trajectories.traces

Loss-bounded GenAI trace normalization and structural integrity checks.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/traces.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [TraceEventKind](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/traces.py#L17) | class | — |
| [TraceLink](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/traces.py#L28) | class | — |
| [TraceEvent](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/traces.py#L40) | class | [duration](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/traces.py#L63) |
| [NormalizedTrace](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/traces.py#L70) | class | — |
| [TraceIntegrityCode](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/traces.py#L79) | class | — |
| [TraceIntegrityIssue](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/traces.py#L89) | class | — |
| [TraceIntegrityReport](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/traces.py#L96) | class | [valid](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/traces.py#L102) |
| [normalize_genai_trace](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/traces.py#L106) | function | — |
| [inspect_trace_integrity](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/traces.py#L166) | function | — |
| [project_tool_trajectory](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/traces.py#L239) | function | — |

### mari_components.trajectories.workflows

Match reviewed intents and safely reuse their knowledge dependencies.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/workflows.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [ReviewedWorkflow](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/workflows.py#L23) | class | — |
| [ReviewedWorkflowMatch](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/workflows.py#L58) | class | — |
| [ReviewedWorkflowIndex](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/workflows.py#L64) | class | — |
| [CacheDecisionReason](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/workflows.py#L72) | class | — |
| [WorkflowAction](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/workflows.py#L79) | class | — |
| [WorkflowDecisionReason](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/workflows.py#L85) | class | — |
| [WorkflowPolicy](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/workflows.py#L96) | class | — |
| [WorkflowDecision](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/workflows.py#L121) | class | [cached_answer](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/workflows.py#L129) |
| [CacheDecision](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/workflows.py#L136) | class | [reusable](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/workflows.py#L143) |
| [build_reviewed_workflow_index](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/workflows.py#L147) | function | — |
| [match_reviewed_workflow](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/workflows.py#L161) | function | — |
| [workflow_freshness](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/workflows.py#L195) | function | — |
| [match_cached_response](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/workflows.py#L211) | function | — |
| [decide_reviewed_workflow](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/workflows.py#L278) | function | — |
| [start_speculative_retrieval](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/workflows.py#L379) | function | — |


## Agent events and evaluation

### mari_components.agents.evaluation

Small, framework-neutral checks over normalized agent events.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/agents/evaluation.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [EvalResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/agents/evaluation.py#L13) | class | — |
| [evaluate_tools](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/agents/evaluation.py#L21) | function | — |
| [evaluate_outcome](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/agents/evaluation.py#L39) | function | — |

### mari_components.agents.events

Small event values for evaluating runs produced by an agent framework.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/agents/events.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [EventKind](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/agents/events.py#L18) | class | — |
| [AgentEvent](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/agents/events.py#L27) | class | — |


## Conformance utilities

### mari_components.testing.connectors

Storage-independent connector contract checks.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/testing/connectors.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [ConnectorContractReport](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/testing/connectors.py#L22) | class | — |
| [check_connector_contract](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/testing/connectors.py#L48) | function | — |
| [check_streaming_connector_contract](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/testing/connectors.py#L91) | function | — |

### mari_components.testing.contracts

Behavioral checks for application-owned boundary implementations.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/testing/contracts.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [assert_clock_conforms](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/testing/contracts.py#L12) | function | — |
| [assert_serializer_conforms](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/testing/contracts.py#L20) | function | — |
| [assert_authorizer_conforms](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/testing/contracts.py#L30) | function | — |
| [assert_index_authorization_conforms](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/testing/contracts.py#L41) | function | — |

### mari_components.testing.stores

Reusable conformance checks for artifact-store adapters.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/testing/stores.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [assert_artifact_store_conforms](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/testing/stores.py#L22) | function | — |
| [assert_document_store_conforms](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/testing/stores.py#L75) | function | — |


## Conversations and topics

### mari_components.conversation_knowledge

Compile conversations and observable trajectories into searchable evidence.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_knowledge.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [KnowledgeEvent](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_knowledge.py#L29) | class | — |
| [KnowledgeEpisode](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_knowledge.py#L52) | class | — |
| [segment_conversations](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_knowledge.py#L68) | function | — |
| [trajectory_events](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_knowledge.py#L138) | function | — |
| [EventEvidence](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_knowledge.py#L174) | class | — |
| [KnowledgeClaim](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_knowledge.py#L183) | class | — |
| [EpisodeKnowledge](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_knowledge.py#L191) | class | [cache_key](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_knowledge.py#L200), [retrieval_units](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_knowledge.py#L203) |
| [extraction_request](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_knowledge.py#L233) | function | — |
| [parse_episode_knowledge](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_knowledge.py#L263) | function | — |
| [CompilationResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_knowledge.py#L370) | class | — |
| [compile_episodes](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_knowledge.py#L377) | function | — |
| [evidence_context](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_knowledge.py#L426) | function | — |
| [topic_history](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_knowledge.py#L451) | function | — |

### mari_components.conversation_topics

Semantic conversation grouping and incremental, evidence-bound topic briefs.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_topics.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [event_vector_key](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_topics.py#L36) | function | — |
| [knowledge_vector_key](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_topics.py#L41) | function | — |
| [semantic_conversation_episodes](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_topics.py#L98) | function | — |
| [TopicGroup](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_topics.py#L152) | class | [scope](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_topics.py#L169), [topic_id](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_topics.py#L173), [revision](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_topics.py#L183) |
| [semantic_topic_groups](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_topics.py#L187) | function | — |
| [ClaimLink](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_topics.py#L224) | class | — |
| [topic_request](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_topics.py#L245) | function | — |
| [TopicBrief](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_topics.py#L269) | class | [cache_key](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_topics.py#L276), [retrieval_units](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_topics.py#L281) |
| [parse_topic_brief](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_topics.py#L310) | function | — |
| [topic_dependencies](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_topics.py#L363) | function | — |
| [TopicCompilation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_topics.py#L397) | class | — |
| [compile_topic_briefs](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_topics.py#L407) | function | — |
| [topic_evidence_context](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/conversation_topics.py#L477) | function | — |


## Documents and source structure

### mari_components.documents

Canonical structured-document and code-graph values.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/__init__.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [ParsedBlock](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/__init__.py#L15) | class | — |
| [ParsedDocument](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/__init__.py#L44) | class | — |
| [ParsedField](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/__init__.py#L67) | class | — |
| [ParsedRecord](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/__init__.py#L87) | class | — |
| [BoundingBox](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/__init__.py#L103) | class | — |
| [RegionKind](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/__init__.py#L121) | class | — |
| [TableCell](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/__init__.py#L133) | class | — |
| [DocumentRegion](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/__init__.py#L147) | class | [searchable_text](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/__init__.py#L165) |
| [RegionRepresentation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/__init__.py#L172) | class | — |
| [RegionEvidence](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/__init__.py#L180) | class | — |
| [StructuredDocument](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/__init__.py#L202) | class | — |
| [CodeSymbolKind](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/__init__.py#L221) | class | — |
| [CodeEdgeKind](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/__init__.py#L230) | class | — |
| [CodeSymbol](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/__init__.py#L240) | class | — |
| [CodeEdge](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/__init__.py#L277) | class | — |
| [CodeReference](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/__init__.py#L284) | class | — |
| [impacted_symbols](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/__init__.py#L305) | function | — |

### mari_components.documents.atoms

Stable semantic atoms, temporal versions, and incremental refresh plans.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/atoms.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [AtomKind](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/atoms.py#L25) | class | — |
| [SemanticAtom](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/atoms.py#L34) | class | [contextual_text](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/atoms.py#L67), [to_revision_ref](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/atoms.py#L71), [located_evidence](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/atoms.py#L79) |
| [TemporalAtom](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/atoms.py#L89) | class | — |
| [AtomDiffAlgorithm](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/atoms.py#L118) | class | — |
| [AtomModification](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/atoms.py#L124) | class | — |
| [AtomAlignment](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/atoms.py#L131) | class | — |
| [AtomRefreshPlan](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/atoms.py#L141) | class | [reuse_embeddings](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/atoms.py#L152), [embed_atom_ids](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/atoms.py#L156) |
| [normalize_atom_text](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/atoms.py#L162) | function | — |
| [semantic_atoms](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/atoms.py#L168) | function | — |
| [content_defined_spans](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/atoms.py#L311) | function | — |
| [align_atoms](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/atoms.py#L349) | function | — |
| [plan_atom_refresh](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/atoms.py#L425) | function | — |
| [active_atoms](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/atoms.py#L504) | function | — |

### mari_components.documents.code

Concrete, dependency-free Python structure extraction.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/code.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [CodeParseResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/code.py#L16) | class | [succeeded](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/code.py#L25) |
| [parse_python](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/code.py#L46) | function | — |

### mari_components.documents.coordinates

Explicit conversion between character and encoded-byte source offsets.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/coordinates.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [SourceCoordinateMap](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/coordinates.py#L10) | class | [build](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/coordinates.py#L15), [character_length](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/coordinates.py#L27), [byte_length](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/coordinates.py#L31), [to_byte](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/coordinates.py#L34), [to_character](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/coordinates.py#L39), [byte_span_to_characters](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/coordinates.py#L53) |
| [line_column](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/coordinates.py#L59) | function | — |

### mari_components.documents.dependencies

Semantic atoms as shared, scoped inputs to any Mari derivation.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/dependencies.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [AtomDependencies](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/dependencies.py#L19) | class | [stamps](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/dependencies.py#L26) |
| [atom_dependencies](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/dependencies.py#L30) | function | — |
| [atom_collection_stamp](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/dependencies.py#L74) | function | — |

### mari_components.documents.docling

Adapt Docling's exported document tree without importing its runtime.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/docling.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [DoclingAdaptation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/docling.py#L37) | class | — |
| [adapt_docling_json](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/docling.py#L44) | function | — |

### mari_components.documents.html

Small HTML-to-block adapter with raw source spans and table topology.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/html.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [parse_html](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/html.py#L215) | function | — |

### mari_components.documents.markdown

Dependency-free structural Markdown parsing with exact character spans.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/markdown.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [parse_markdown](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/markdown.py#L48) | function | — |

### mari_components.documents.records

Delimited and JSON Lines records with exact source coordinates.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/records.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [parse_delimited](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/records.py#L46) | function | — |
| [parse_json_lines](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/records.py#L203) | function | — |
| [parse_json_array](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/records.py#L280) | function | — |

### mari_components.documents.results

Parser-neutral results, issues, and stable source identities.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/results.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [ParseIssueSeverity](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/results.py#L59) | class | — |
| [ParseIssue](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/results.py#L65) | class | — |
| [ParseResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/results.py#L85) | class | [succeeded](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/results.py#L100) |
| [stable_source_id](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/results.py#L106) | function | — |

### mari_components.documents.sequence_diff

Myers and patience sequence alignment with coalesced edit spans.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/sequence_diff.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [DiffKind](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/sequence_diff.py#L14) | class | — |
| [DiffSpan](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/sequence_diff.py#L22) | class | — |
| [myers_diff](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/sequence_diff.py#L30) | function | — |
| [patience_diff](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/sequence_diff.py#L58) | function | — |

### mari_components.documents.tables

Table topology normalization without format or domain assumptions.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/tables.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [NormalizedTable](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/tables.py#L11) | class | — |
| [normalize_table](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/tables.py#L17) | function | — |

### mari_components.documents.validation

Structural validation for parser-neutral document values.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/validation.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [StructureViolation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/validation.py#L19) | class | — |
| [StructureValidationReport](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/validation.py#L26) | class | [conforms](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/validation.py#L30) |
| [validate_parsed_document](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/validation.py#L66) | function | — |
| [validate_structured_document](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/validation.py#L113) | function | — |
| [RegionEvidenceResolution](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/validation.py#L135) | class | [valid](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/validation.py#L146) |
| [validate_region_evidence](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/documents/validation.py#L150) | function | — |


## Evaluation and statistics

### mari_components.evaluation.cases

Normalized cases and adapters for public knowledge-system corpora.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/cases.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [RetrievalCase](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/cases.py#L17) | class | — |
| [EvidenceCase](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/cases.py#L29) | class | — |
| [MemoryCase](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/cases.py#L37) | class | — |
| [load_beir_cases](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/cases.py#L70) | function | — |
| [load_fever_cases](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/cases.py#L95) | function | — |
| [load_longmemeval_cases](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/cases.py#L122) | function | — |
| [group_memory_cases](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/cases.py#L154) | function | — |

### mari_components.evaluation.catalog

Read and validate Mari benchmark corpus catalogs.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/catalog.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [Corpus](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/catalog.py#L14) | class | — |
| [CorpusCatalog](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/catalog.py#L28) | class | [for_task](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/catalog.py#L46) |
| [load_catalog](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/catalog.py#L83) | function | — |
| [catalog_rows](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/catalog.py#L100) | function | — |

### mari_components.evaluation.gates

Hard regression gates for benchmark reports.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/gates.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [GateMode](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/gates.py#L11) | class | — |
| [MetricGate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/gates.py#L18) | class | — |
| [GateCheck](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/gates.py#L36) | class | — |
| [GateReport](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/gates.py#L45) | class | — |
| [regression_gate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/gates.py#L50) | function | — |

### mari_components.evaluation.graph

Component metrics for graph construction and selection.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/graph.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [LinkPredictionMetrics](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/graph.py#L12) | class | — |
| [PathMetrics](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/graph.py#L19) | class | — |
| [evaluate_path](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/graph.py#L27) | function | — |
| [evaluate_link_prediction](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/graph.py#L44) | function | — |
| [evaluate_subgraph](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/graph.py#L70) | function | — |
| [ClusteringMetrics](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/graph.py#L77) | class | — |
| [GraphContextMetrics](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/graph.py#L85) | class | — |
| [GroupCoverage](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/graph.py#L93) | class | — |
| [GroupedCoverageMetrics](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/graph.py#L102) | class | — |
| [evaluate_grouped_coverage](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/graph.py#L108) | function | — |
| [evaluate_graph_context](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/graph.py#L146) | function | — |
| [evaluate_clustering](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/graph.py#L185) | function | — |

### mari_components.evaluation.metrics

Deterministic metrics for retrieval and labeled decisions.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/metrics.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [RetrievalMetrics](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/metrics.py#L11) | class | — |
| [ClassificationMetrics](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/metrics.py#L19) | class | — |
| [SetMetrics](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/metrics.py#L28) | class | — |
| [TaskOutcome](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/metrics.py#L38) | class | — |
| [TaskOutcomeComparison](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/metrics.py#L52) | class | — |
| [compare_task_outcomes](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/metrics.py#L61) | function | — |
| [set_metrics](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/metrics.py#L88) | function | — |
| [boundary_metrics](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/metrics.py#L111) | function | — |
| [reciprocal_rank](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/metrics.py#L152) | function | — |
| [ndcg_at_k](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/metrics.py#L161) | function | — |
| [evaluate_retrieval](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/metrics.py#L185) | function | — |
| [classification_metrics](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/metrics.py#L206) | function | — |

### mari_components.evaluation.runs

Reproducibility metadata for persisted evaluation outputs.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/runs.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [EvaluationRun](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/runs.py#L15) | class | — |

### mari_components.evaluation.statistics

Paired uncertainty, slice summaries, reliability, and repeated-trial metrics.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/statistics.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [PairedMetric](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/statistics.py#L14) | class | — |
| [PairedMetricComparison](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/statistics.py#L29) | class | — |
| [SliceComparison](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/statistics.py#L42) | class | — |
| [ReviewLabel](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/statistics.py#L49) | class | — |
| [ReviewReliability](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/statistics.py#L56) | class | — |
| [RepeatedTrialResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/statistics.py#L67) | class | — |
| [PassKSummary](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/statistics.py#L73) | class | — |
| [compare_paired_metrics](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/statistics.py#L80) | function | — |
| [evaluate_slices](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/statistics.py#L116) | function | — |
| [summarize_review_reliability](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/statistics.py#L147) | function | — |
| [summarize_repeated_trials](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/statistics.py#L194) | function | — |

### mari_components.evaluation.suites

Machine-readable mappings from papers and APIs to benchmark contracts.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/suites.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [BenchmarkSuite](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/suites.py#L11) | class | — |
| [BenchmarkSuiteCatalog](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/suites.py#L20) | class | [get](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/suites.py#L24), [for_paper](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/suites.py#L30) |
| [load_suite_catalog](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/suites.py#L34) | function | — |


## Governance policies

### mari_components.governance

Trust, authority, scope, and retention policy primitives.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [TrustLevel](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L15) | class | — |
| [WriteChannel](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L22) | class | — |
| [ContentInterpretation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L31) | class | — |
| [WriteDisposition](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L38) | class | — |
| [MemoryWrite](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L45) | class | — |
| [WriteDecision](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L67) | class | — |
| [evaluate_write](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L73) | function | — |
| [inherit_taints](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L107) | function | — |
| [SourceAssertion](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L112) | class | — |
| [AuthorityPolicy](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L142) | class | — |
| [AssertionResolution](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L159) | class | — |
| [resolve_assertions](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L166) | function | — |
| [ScopeGrant](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L219) | class | — |
| [ScopePolicy](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L226) | class | [allows](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L229) |
| [PromotionProposal](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L243) | class | — |
| [propose_promotion](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L252) | function | — |
| [RetentionRecord](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L281) | class | — |
| [RetentionPolicy](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L290) | class | — |
| [RetentionActionKind](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L302) | class | — |
| [RetentionAction](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L309) | class | — |
| [RetentionPlan](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L316) | class | — |
| [PurposeDecision](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L321) | class | — |
| [evaluate_purpose](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L326) | function | — |
| [plan_retention](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/governance/__init__.py#L336) | function | — |


## Graph algorithms and interchange

### mari_components.graph.adjacency

Adjacency projections over caller-owned edge iterables.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/adjacency.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [build_adjacency](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/adjacency.py#L13) | function | — |

### mari_components.graph.centrality

Reference centrality algorithms over neighbor callbacks.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/centrality.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [degree_centrality](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/centrality.py#L13) | function | — |
| [closeness_centrality](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/centrality.py#L26) | function | — |
| [betweenness_centrality](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/centrality.py#L51) | function | — |
| [hits](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/centrality.py#L97) | function | — |

### mari_components.graph.communities

Deterministic graph communities and model-injected corpus aggregation.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/communities.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [CommunityPartition](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/communities.py#L12) | class | — |
| [CommunityReport](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/communities.py#L18) | class | — |
| [leiden_communities](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/communities.py#L87) | function | — |
| [build_community_reports](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/communities.py#L152) | function | — |
| [map_reduce_reports](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/communities.py#L172) | function | — |

### mari_components.graph.construction

Deterministic blocking and threshold clustering for caller-owned entities.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/construction.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [BlockedPair](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/construction.py#L14) | class | — |
| [explain_candidate_pairs](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/construction.py#L20) | function | — |
| [candidate_pairs](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/construction.py#L46) | function | — |
| [MatchLink](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/construction.py#L62) | class | — |
| [ClusterResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/construction.py#L69) | class | — |
| [EvidenceBoundCandidate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/construction.py#L77) | class | — |
| [EvidenceResolution](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/construction.py#L85) | class | — |
| [ClusterDiagnostic](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/construction.py#L91) | class | — |
| [resolve_relation_evidence](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/construction.py#L97) | function | — |
| [bind_relation_evidence](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/construction.py#L110) | function | — |
| [cluster_matches](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/construction.py#L131) | function | — |
| [inspect_clusters](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/construction.py#L191) | function | — |

### mari_components.graph.diagnostics

Exact graph diffs and policy-neutral structural observations.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/diagnostics.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [GraphDiff](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/diagnostics.py#L15) | class | — |
| [graph_diff](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/diagnostics.py#L29) | function | — |
| [RecordChange](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/diagnostics.py#L49) | class | — |
| [RecordDiff](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/diagnostics.py#L56) | class | — |
| [FieldChange](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/diagnostics.py#L64) | class | — |
| [diff_record_fields](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/diagnostics.py#L71) | function | — |
| [diff_records](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/diagnostics.py#L110) | function | — |
| [GraphQualityReport](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/diagnostics.py#L149) | class | — |
| [inspect_graph_quality](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/diagnostics.py#L159) | function | — |

### mari_components.graph.evidence_projection

Many-to-many projections from graph values to evidence artifacts.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/evidence_projection.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [GraphEvidenceAssociation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/evidence_projection.py#L16) | class | — |
| [GraphEvidenceProjection](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/evidence_projection.py#L25) | class | [artifact_refs](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/evidence_projection.py#L30) |
| [project_graph_evidence](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/evidence_projection.py#L38) | function | — |

### mari_components.graph.interop

Transient graph projections and loss-visible interchange encoders.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/interop.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [ProjectionEdge](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/interop.py#L19) | class | — |
| [GraphProjection](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/interop.py#L32) | class | — |
| [InterchangeReport](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/interop.py#L49) | class | — |
| [EncodedGraph](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/interop.py#L54) | class | — |
| [to_graphml](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/interop.py#L81) | function | — |
| [to_json_ld](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/interop.py#L176) | function | — |
| [to_networkx](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/interop.py#L203) | function | — |
| [from_networkx](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/interop.py#L227) | function | — |
| [to_rdflib](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/interop.py#L252) | function | — |
| [to_pyg_data](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/interop.py#L283) | function | — |

### mari_components.graph.provenance

Bounded lineage and taint traversal over arbitrary artifact IDs.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/provenance.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [LineageVisit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/provenance.py#L16) | class | — |
| [LineageTrace](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/provenance.py#L23) | class | — |
| [LineageEdge](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/provenance.py#L30) | class | — |
| [LineageEdgeTrace](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/provenance.py#L44) | class | — |
| [trace_lineage_edges](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/provenance.py#L51) | function | — |
| [trace_lineage](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/provenance.py#L99) | function | — |
| [propagated_taints](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/provenance.py#L140) | function | — |

### mari_components.graph.resolution

Fellegi--Sunter entity-resolution scoring with explicit review bands.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/resolution.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [FieldAgreement](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/resolution.py#L12) | class | — |
| [ResolutionDecision](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/resolution.py#L28) | class | — |
| [ResolutionResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/resolution.py#L35) | class | — |
| [fellegi_sunter_score](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/resolution.py#L43) | function | — |
| [resolve_entity](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/resolution.py#L68) | function | — |

### mari_components.graph.similarity

Topology-only link-candidate scoring.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/similarity.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [LinkScore](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/similarity.py#L14) | class | — |
| [score_link_candidates](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/similarity.py#L22) | function | — |
| [simrank_scores](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/similarity.py#L62) | function | — |

### mari_components.graph.subgraphs

Budgeted selection over caller-owned graph topology.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/subgraphs.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [SubgraphSelection](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/subgraphs.py#L16) | class | — |
| [bounded_seed_expansion](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/subgraphs.py#L25) | function | — |
| [prize_guided_subgraph](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/subgraphs.py#L78) | function | — |

### mari_components.graph.temporal

Append-only bi-temporal fact operations.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/temporal.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [TemporalFact](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/temporal.py#L20) | class | — |
| [close_transaction](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/temporal.py#L59) | function | — |
| [query_temporal_facts](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/temporal.py#L67) | function | — |

### mari_components.graph.temporal_tools

Half-open interval operations independent of graph representation.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/temporal_tools.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [TimeInterval](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/temporal_tools.py#L17) | class | — |
| [interval_contains](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/temporal_tools.py#L31) | function | — |
| [intervals_overlap](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/temporal_tools.py#L39) | function | — |
| [close_interval](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/temporal_tools.py#L43) | function | — |
| [interval_intersection](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/temporal_tools.py#L51) | function | — |
| [TemporalJoinPair](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/temporal_tools.py#L64) | class | — |
| [IntervalOverlapPair](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/temporal_tools.py#L71) | class | — |
| [grouped_interval_overlaps](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/temporal_tools.py#L78) | function | — |
| [temporal_join](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/temporal_tools.py#L125) | function | — |

### mari_components.graph.traversal

Graph traversal over caller-owned node IDs and neighbor callbacks.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/traversal.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [TraversalVisit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/traversal.py#L21) | class | — |
| [TraversalResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/traversal.py#L28) | class | [nodes](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/traversal.py#L33) |
| [PathResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/traversal.py#L38) | class | [found](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/traversal.py#L45) |
| [CycleResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/traversal.py#L50) | class | — |
| [PredecessorEntry](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/traversal.py#L56) | class | — |
| [PredecessorDAG](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/traversal.py#L64) | class | — |
| [EdgeTraversalVisit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/traversal.py#L70) | class | — |
| [RejectedTraversalEdge](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/traversal.py#L77) | class | — |
| [EdgeTraversalResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/traversal.py#L83) | class | — |
| [traverse_edges](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/traversal.py#L90) | function | — |
| [predecessor_dag](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/traversal.py#L169) | function | — |
| [breadth_first](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/traversal.py#L232) | function | — |
| [k_hop_nodes](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/traversal.py#L267) | function | — |
| [shortest_path](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/traversal.py#L284) | function | — |
| [connected_components](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/traversal.py#L335) | function | — |
| [directed_cycles](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/traversal.py#L359) | function | — |


## Incremental maintenance

### mari_components.aggregates

Reversible, keyed delta aggregates with exact arithmetic for numeric sums.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [DeltaReducer](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L18) | class | [zero](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L21), [change](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L22), [finish](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L23) |
| [DeltaAggregate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L26) | class | [apply](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L40), [value](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L71), [contributions](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L75), [stamp](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L78) |
| [CountReducer](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L86) | class | [zero](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L87), [change](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L90), [finish](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L93) |
| [VectorTotals](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L98) | class | — |
| [WeightedVectorReducer](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L104) | class | [zero](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L111), [change](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L114), [finish](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L137) |
| [LexicalTotals](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L149) | class | — |
| [LexicalStatisticsReducer](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L167) | class | [zero](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L170), [change](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L173), [finish](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L185) |
| [MembershipReducer](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L194) | class | [zero](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L201), [change](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L204), [finish](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/aggregates.py#L215) |

### mari_components.dependencies

Shared dependency receipts and incremental planning for derived material.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/dependencies.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [dependency_fingerprint](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/dependencies.py#L21) | function | — |
| [DependencyKey](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/dependencies.py#L27) | class | [key](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/dependencies.py#L41), [from_revision](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/dependencies.py#L45) |
| [DependencyStamp](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/dependencies.py#L50) | class | [from_revision](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/dependencies.py#L59) |
| [DerivationSpec](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/dependencies.py#L66) | class | [fingerprint](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/dependencies.py#L90) |
| [MaterializationReceipt](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/dependencies.py#L97) | class | — |
| [materialization_receipt](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/dependencies.py#L113) | function | — |
| [UpdateAction](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/dependencies.py#L130) | class | — |
| [DependencyUpdate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/dependencies.py#L138) | class | — |
| [DependencyUpdatePlan](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/dependencies.py#L147) | class | [ready](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/dependencies.py#L153), [reusable](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/dependencies.py#L159) |
| [plan_dependency_updates](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/dependencies.py#L165) | function | — |

### mari_components.grouping

Deterministic overlap lineage across episode/topic/community regrouping.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/grouping.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [GroupIdentity](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/grouping.py#L15) | class | — |
| [GroupAssignment](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/grouping.py#L29) | class | — |
| [GroupReconciliation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/grouping.py#L37) | class | — |
| [reconcile_groups](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/grouping.py#L42) | function | — |

### mari_components.incremental

Indexed, process-local dependency planning. Persistence remains host-owned.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/incremental.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [DependencyIndex](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/incremental.py#L21) | class | [apply](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/incremental.py#L58), [plan](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/incremental.py#L189) |

### mari_components.selections

Conservative selection dependencies, including previously unseen members.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/selections.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [SelectionSpec](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/selections.py#L24) | class | [output](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/selections.py#L44) |
| [SelectionPlan](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/selections.py#L49) | class | — |
| [SelectionReceipt](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/selections.py#L57) | class | [consumer_inputs](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/selections.py#L65) |
| [plan_selection](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/selections.py#L70) | function | — |
| [complete_selection](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/selections.py#L127) | function | — |


## Knowledge and memory

### mari_components.knowledge.admission

Evidence and safety admission before memory reconciliation.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/admission.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [AdmissionDisposition](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/admission.py#L10) | class | — |
| [AdmissionSignals](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/admission.py#L18) | class | — |
| [AdmissionThresholds](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/admission.py#L33) | class | — |
| [AdmissionDecision](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/admission.py#L43) | class | — |
| [admit_candidate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/admission.py#L48) | function | — |

### mari_components.knowledge.aggregation

Policy-neutral scalar uncertainty and weighted aggregation utilities.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/aggregation.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [ScalarEstimate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/aggregation.py#L11) | class | — |
| [WeightedObservation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/aggregation.py#L31) | class | — |
| [WeightedContribution](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/aggregation.py#L47) | class | — |
| [WeightedMean](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/aggregation.py#L57) | class | — |
| [weighted_mean](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/aggregation.py#L64) | function | — |
| [wilson_proportion](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/aggregation.py#L93) | function | — |

### mari_components.knowledge.answers

Grounded answer generation and reusable FAQ candidate mining.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/answers.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [AnswerDisposition](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/answers.py#L22) | class | — |
| [GroundedAnswer](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/answers.py#L28) | class | [knowledge_dependencies](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/answers.py#L65) |
| [parse_answer](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/answers.py#L69) | function | — |
| [parse_answer_candidates](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/answers.py#L117) | function | — |

### mari_components.knowledge.artifacts

Generic immutable envelopes for governed knowledge artifacts.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/artifacts.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [ArtifactRef](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/artifacts.py#L20) | class | [key](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/artifacts.py#L34), [to_revision_ref](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/artifacts.py#L45) |
| [ReviewState](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/artifacts.py#L57) | class | — |
| [Activity](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/artifacts.py#L67) | class | — |
| [KnowledgeArtifact](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/artifacts.py#L81) | class | [ref](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/artifacts.py#L133), [derivation_spec](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/artifacts.py#L141) |

### mari_components.knowledge.assertions

Evidence-bearing temporal assertions and caller-selected update plans.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/assertions.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [Assertion](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/assertions.py#L22) | class | — |
| [group_assertions](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/assertions.py#L43) | function | — |
| [AssertionUpdateKind](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/assertions.py#L65) | class | — |
| [AssertionUpdatePlan](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/assertions.py#L73) | class | — |
| [plan_assertion_update](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/assertions.py#L81) | function | — |
| [valid_at](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/assertions.py#L112) | function | — |
| [all_of](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/assertions.py#L131) | function | — |
| [any_of](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/assertions.py#L135) | function | — |

### mari_components.knowledge.changesets

Cross-document edit validation with previews and inverse operations.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/changesets.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [PositionedKnowledgeEdit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/changesets.py#L16) | class | — |
| [KnowledgeChangeEntry](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/changesets.py#L23) | class | — |
| [ChangesetIssueKind](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/changesets.py#L32) | class | — |
| [ChangesetIssue](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/changesets.py#L40) | class | — |
| [KnowledgeChangeset](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/changesets.py#L47) | class | [valid](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/changesets.py#L53) |
| [validate_knowledge_changeset](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/changesets.py#L57) | function | — |

### mari_components.knowledge.citations

Inspect citation declarations against explicit evidence event ordering.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/citations.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [OwnedEvidenceRef](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/citations.py#L17) | class | — |
| [CitationEventKind](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/citations.py#L26) | class | — |
| [CitationEvent](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/citations.py#L32) | class | — |
| [CitationDeclarationStatus](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/citations.py#L62) | class | — |
| [CitationDeclarationReport](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/citations.py#L71) | class | — |
| [inspect_citation_declarations](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/citations.py#L80) | function | — |

### mari_components.knowledge.compaction

Plan conversation evidence retention without rewriting stored history.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/compaction.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [CompactionEvidence](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/compaction.py#L19) | class | [key](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/compaction.py#L42) |
| [CompactionExclusion](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/compaction.py#L46) | class | — |
| [CompactionTrace](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/compaction.py#L54) | class | — |
| [EvidenceGroup](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/compaction.py#L61) | class | — |
| [EvidenceCompactionPlan](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/compaction.py#L67) | class | — |
| [plan_evidence_compaction](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/compaction.py#L76) | function | — |

### mari_components.knowledge.consolidation

Budgeted, model-neutral consolidation and promotion planning.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/consolidation.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [PromotionSignal](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/consolidation.py#L11) | class | — |
| [ConsolidationBudget](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/consolidation.py#L36) | class | — |
| [ConsolidationPlan](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/consolidation.py#L46) | class | — |
| [plan_consolidation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/consolidation.py#L54) | function | — |

### mari_components.knowledge.decisions

Product decision extraction with source evidence.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/decisions.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [parse_decisions](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/decisions.py#L17) | function | — |

### mari_components.knowledge.derivations

Provenance checks that keep derived knowledge from becoming fresh evidence.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/derivations.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [KnowledgeOrigin](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/derivations.py#L12) | class | — |
| [DerivationInput](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/derivations.py#L18) | class | — |
| [KnowledgeDerivation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/derivations.py#L24) | class | — |
| [DerivationIssueKind](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/derivations.py#L35) | class | — |
| [DerivationIssue](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/derivations.py#L43) | class | — |
| [DerivationReport](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/derivations.py#L50) | class | [valid](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/derivations.py#L55) |
| [inspect_knowledge_derivations](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/derivations.py#L59) | function | — |

### mari_components.knowledge.evidence

Artifact-neutral evidence resolution and exact-material validation.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/evidence.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [ArtifactEvidence](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/evidence.py#L28) | class | — |
| [LocatedEvidenceIssue](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/evidence.py#L46) | class | — |
| [LocatedEvidenceReport](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/evidence.py#L53) | class | [accepted](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/evidence.py#L58) |
| [document_evidence_ref](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/evidence.py#L62) | function | — |
| [EvidenceIssueKind](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/evidence.py#L81) | class | — |
| [EvidenceIssue](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/evidence.py#L90) | class | — |
| [EvidenceValidationReport](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/evidence.py#L97) | class | [accepted](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/evidence.py#L102) |
| [validate_artifact_evidence](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/evidence.py#L106) | function | — |
| [validate_located_evidence](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/evidence.py#L211) | function | — |

### mari_components.knowledge.excerpt

Extract a clean prose preview from Markdown or HTML knowledge content.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/excerpt.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [excerpt](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/excerpt.py#L55) | function | — |

### mari_components.knowledge.experience

Turn trajectory evidence and expert feedback into reviewable knowledge changes.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/experience.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [TrajectoryEvidence](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/experience.py#L22) | class | — |
| [KnowledgeUse](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/experience.py#L29) | class | — |
| [KnowledgeUseManifest](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/experience.py#L38) | class | — |
| [ExpertFeedback](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/experience.py#L44) | class | — |
| [FeedbackRootCause](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/experience.py#L50) | class | — |
| [FeedbackDiagnosis](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/experience.py#L59) | class | — |
| [ExperienceKnowledgeKind](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/experience.py#L68) | class | — |
| [ExperienceKnowledgeCandidate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/experience.py#L76) | class | — |
| [KnowledgeFile](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/experience.py#L87) | class | — |
| [KnowledgeStructureIssueKind](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/experience.py#L95) | class | — |
| [KnowledgeStructureIssue](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/experience.py#L104) | class | — |
| [KnowledgeStructureReport](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/experience.py#L111) | class | [valid](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/experience.py#L116) |
| [KnowledgeEdit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/experience.py#L121) | class | — |
| [KnowledgeChangeProposal](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/experience.py#L130) | class | — |
| [ChangeEvaluation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/experience.py#L138) | class | [targeted_delta](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/experience.py#L146), [regression_delta](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/experience.py#L150) |
| [build_knowledge_use_manifest](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/experience.py#L154) | function | — |
| [parse_feedback_diagnoses](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/experience.py#L188) | function | — |
| [parse_experience_knowledge](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/experience.py#L264) | function | — |
| [inspect_knowledge_structure](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/experience.py#L311) | function | — |
| [parse_knowledge_change](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/experience.py#L407) | function | — |

### mari_components.knowledge.fact_scans

Content-addressed, passage-level planning for incremental fact extraction.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/fact_scans.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [pending_fact_sections](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/fact_scans.py#L14) | function | — |
| [fact_scan_revisions](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/fact_scans.py#L65) | function | — |

### mari_components.knowledge.facts

Fact extraction and evidence-based claim assessment.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/facts.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [normalize_claim](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/facts.py#L23) | function | — |
| [parse_facts](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/facts.py#L97) | function | — |
| [FactAssessment](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/facts.py#L149) | class | — |
| [parse_claim_assessments](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/facts.py#L158) | function | — |
| [deduplicate_fact_candidates](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/facts.py#L218) | function | — |

### mari_components.knowledge.freshness

Fine-grained dependency and change-impact decisions for governed knowledge.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/freshness.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [FreshnessStatus](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/freshness.py#L14) | class | — |
| [KnowledgeDependency](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/freshness.py#L22) | class | [dependency_id](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/freshness.py#L39) |
| [RevisionChange](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/freshness.py#L48) | class | [dependency_id](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/freshness.py#L55) |
| [FreshnessReport](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/freshness.py#L64) | class | [reusable](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/freshness.py#L71) |
| [ReferenceRevisionChange](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/freshness.py#L76) | class | — |
| [ReferenceFreshnessReport](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/freshness.py#L82) | class | [reusable](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/freshness.py#L88) |
| [assess_revision_refs](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/freshness.py#L92) | function | — |
| [evidence_dependencies](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/freshness.py#L118) | function | — |
| [assess_dependencies](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/freshness.py#L140) | function | — |
| [assess_freshness](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/freshness.py#L199) | function | — |
| [impacted_artifacts](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/freshness.py#L213) | function | — |

### mari_components.knowledge.glossary

Evidence-backed glossary harvesting.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/glossary.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [parse_glossary](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/glossary.py#L16) | function | — |

### mari_components.knowledge.links

Explicit-reference parsing and caller-scored semantic link selection.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/links.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [LinkCandidate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/links.py#L18) | class | — |
| [extract_explicit_links](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/links.py#L40) | function | — |
| [derive_links](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/links.py#L60) | function | — |

### mari_components.knowledge.multimodal

Revision-bound asset selection; byte loading and message rendering stay external.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/multimodal.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [EvidenceAsset](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/multimodal.py#L15) | class | — |
| [AssetBinding](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/multimodal.py#L34) | class | — |
| [RetainedAsset](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/multimodal.py#L51) | class | — |
| [AssetSelection](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/multimodal.py#L58) | class | — |
| [select_evidence_assets](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/multimodal.py#L63) | function | — |

### mari_components.knowledge.mutations

Validated, storage-neutral memory mutation plans.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/mutations.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [MemoryOperation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/mutations.py#L13) | class | — |
| [MemoryDecision](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/mutations.py#L21) | class | — |
| [MemoryMutation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/mutations.py#L30) | class | — |
| [MemoryMutationPlan](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/mutations.py#L39) | class | [writes](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/mutations.py#L43), [deletes](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/mutations.py#L51), [noops](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/mutations.py#L57) |
| [plan_memory_mutations](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/mutations.py#L63) | function | — |
| [apply_memory_mutations](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/mutations.py#L122) | function | — |

### mari_components.knowledge.observations

Immutable records of how knowledge moved through one observed task.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/observations.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [KnowledgeObservationStage](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/observations.py#L10) | class | — |
| [KnowledgeObservation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/observations.py#L18) | class | — |
| [ObservationIssueKind](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/observations.py#L43) | class | — |
| [ObservationIssue](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/observations.py#L50) | class | — |
| [KnowledgeObservationReport](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/observations.py#L57) | class | [valid](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/observations.py#L66) |
| [inspect_knowledge_observations](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/observations.py#L70) | function | — |

### mari_components.knowledge.refinement

Bounded, exact-substring document refinement proposals.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/refinement.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [RefinementEdit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/refinement.py#L15) | class | — |
| [parse_refinement](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/refinement.py#L22) | function | — |

### mari_components.knowledge.research

Deterministic memory organization and retrieval policies from research.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/research.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [NoteEvolutionPlan](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/research.py#L11) | class | — |
| [plan_note_evolution](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/research.py#L20) | function | — |
| [MemorySignal](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/research.py#L67) | class | — |
| [SalientMemory](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/research.py#L77) | class | — |
| [rank_salient_memories](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/research.py#L87) | function | — |

### mari_components.knowledge.scoring

Deterministic scores derived from validated evidence, never model opinion.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/scoring.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [grounding_coverage](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/scoring.py#L13) | function | — |

### mari_components.knowledge.sections

Deterministic Markdown sections for fine-grained knowledge dependencies.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/sections.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [document_sections](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/sections.py#L23) | function | — |
| [section_revisions](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/sections.py#L89) | function | — |

### mari_components.knowledge.segmentation

Topic-aware segmentation for bounded memory consolidation.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/segmentation.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [TopicSegment](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/segmentation.py#L14) | class | — |
| [hybrid_topic_segments](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/segmentation.py#L20) | function | — |

### mari_components.knowledge.summaries

Digest summarization and evidence-linked impact assessment.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/summaries.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [DigestTopic](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/summaries.py#L19) | class | — |
| [DigestSummary](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/summaries.py#L26) | class | — |
| [ImpactAssessment](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/summaries.py#L34) | class | — |
| [parse_digest](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/summaries.py#L41) | function | — |
| [parse_impact](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/summaries.py#L80) | function | — |

### mari_components.knowledge.tags

Workspace-defined document tags and retrieval behavior.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/tags.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [normalize_tag](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/tags.py#L14) | function | — |
| [TagDefinition](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/tags.py#L23) | class | — |
| [TagAssignments](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/tags.py#L42) | class | [tags_for](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/tags.py#L59) |
| [assign_tags](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/tags.py#L63) | function | — |
| [search_weight](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/tags.py#L88) | function | — |

### mari_components.knowledge.versions

Grouping and representative proposals for immutable manifestations.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/versions.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [VersionFamily](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/versions.py#L14) | class | — |
| [resolve_version_families](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/versions.py#L22) | function | — |


## Platform composition and reference storage

### mari_components.platform.compiler

Constraint-first search over externally evaluated knowledge configurations.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/compiler.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [ObjectiveDirection](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/compiler.py#L16) | class | — |
| [MetricObjective](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/compiler.py#L22) | class | — |
| [CompileCandidate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/compiler.py#L47) | class | — |
| [CompileResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/compiler.py#L57) | class | — |
| [compile_configurations](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/compiler.py#L63) | function | — |

### mari_components.platform.pipeline

Small deterministic pipeline runner with visible stage failures.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/pipeline.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [Stage](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/pipeline.py#L14) | class | [fingerprint](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/pipeline.py#L28) |
| [StageTrace](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/pipeline.py#L40) | class | — |
| [PipelineResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/pipeline.py#L50) | class | [succeeded](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/pipeline.py#L55) |
| [Pipeline](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/pipeline.py#L60) | class | [run](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/pipeline.py#L70) |

### mari_components.platform.projections

Ordered event replay into disposable deterministic projections.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/projections.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [KnowledgeEvent](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/projections.py#L16) | class | — |
| [ProjectionBuild](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/projections.py#L29) | class | — |
| [replay_projection](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/projections.py#L36) | function | — |

### mari_components.platform.stores

Reference in-memory store for revision and point-in-time conformance.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [RevisionConflict](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L15) | class | — |
| [StoreCapabilities](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L20) | class | — |
| [ArtifactStore](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L28) | class | [capabilities](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L32), [commit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L34), [get](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L41), [at_time](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L45), [history](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L53) |
| [DocumentStore](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L59) | class | [capabilities](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L63), [commit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L65), [get](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L73), [resolve](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L77), [history](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L79) |
| [InMemoryDocumentStore](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L84) | class | [capabilities](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L93), [commit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L107), [get](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L124), [resolve](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L130), [history](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L141) |
| [InMemoryArtifactStore](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L147) | class | [capabilities](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L156), [commit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L168), [get](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L191), [at_time](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L197), [history](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/stores.py#L218) |

### mari_components.platform.views

Dependency-aware materialized-view refresh planning.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/views.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [MaterializedView](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/views.py#L22) | class | — |
| [ViewMaterialization](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/views.py#L33) | class | — |
| [ViewRefreshTask](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/views.py#L41) | class | — |
| [ViewRefreshPlan](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/views.py#L47) | class | — |
| [plan_view_refresh](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/views.py#L53) | function | — |

### mari_components.portability

Deterministic in-memory knowledge bundles and import planning.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/portability.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [KnowledgeBundle](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/portability.py#L20) | class | — |
| [BundleVerification](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/portability.py#L28) | class | — |
| [BundleImportPlan](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/portability.py#L34) | class | — |
| [export_bundle](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/portability.py#L44) | function | — |
| [verify_bundle](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/portability.py#L72) | function | — |
| [plan_bundle_import](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/portability.py#L90) | function | — |


## Retrieval and context

### mari_components.lifecycle

Framework-neutral context lifecycle contracts.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/lifecycle.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [LifecyclePhase](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/lifecycle.py#L13) | class | — |
| [InterventionDisposition](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/lifecycle.py#L19) | class | — |
| [ContextRequest](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/lifecycle.py#L25) | class | — |
| [LifecycleEvent](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/lifecycle.py#L50) | class | — |
| [ContextIntervention](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/lifecycle.py#L63) | class | [text](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/lifecycle.py#L79) |
| [select_intervention](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/lifecycle.py#L83) | function | — |
| [ContextProvider](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/lifecycle.py#L102) | class | [before_model](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/lifecycle.py#L105), [after_model](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/lifecycle.py#L107), [after_tool](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/lifecycle.py#L109), [end_session](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/lifecycle.py#L111) |

### mari_components.retrieval.atoms

Atom-hit aggregation and retrieval-time context assembly.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/atoms.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [AtomVectorHit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/atoms.py#L19) | class | — |
| [ParentVectorHit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/atoms.py#L36) | class | — |
| [aggregate_atom_hits](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/atoms.py#L43) | function | — |
| [MultiVectorSection](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/atoms.py#L85) | class | [matrix](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/atoms.py#L103) |
| [maxsim_section_score](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/atoms.py#L120) | function | — |
| [DynamicContextChunk](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/atoms.py#L141) | class | — |
| [DynamicContextResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/atoms.py#L151) | class | — |
| [assemble_atom_context](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/atoms.py#L158) | function | — |

### mari_components.retrieval.composition

Typed handoffs from ranked IDs to artifact-neutral context material.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/composition.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [RetrievalUnit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/composition.py#L20) | class | [from_atom](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/composition.py#L31) |
| [HydratedHit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/composition.py#L54) | class | — |
| [hydrate_hits](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/composition.py#L63) | function | — |
| [ContextItem](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/composition.py#L98) | class | — |
| [ContextSelectionTrace](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/composition.py#L121) | class | — |
| [ContextSelection](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/composition.py#L128) | class | [visible_refs](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/composition.py#L137), [render](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/composition.py#L140) |
| [DiverseSelectionTrace](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/composition.py#L145) | class | — |
| [DiverseCandidateEvaluation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/composition.py#L155) | class | — |
| [DiverseSelectionRound](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/composition.py#L163) | class | — |
| [DiverseContextSelection](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/composition.py#L172) | class | [visible_refs](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/composition.py#L187), [render](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/composition.py#L190) |
| [select_context](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/composition.py#L194) | function | — |
| [select_context_diverse](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/composition.py#L235) | function | — |

### mari_components.retrieval.context

Auditable whole-excerpt context packing under explicit budgets.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/context.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [ContextCandidate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/context.py#L12) | class | — |
| [ContextBudget](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/context.py#L35) | class | — |
| [ContextExclusion](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/context.py#L44) | class | — |
| [ContextTrace](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/context.py#L52) | class | — |
| [ContextEnvelope](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/context.py#L60) | class | — |
| [assemble_context](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/context.py#L68) | function | — |

### mari_components.retrieval.contextual

Revision-bound contextual representations that preserve original source text.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/contextual.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [ContextualRepresentation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/contextual.py#L19) | class | — |
| [parse_chunk_context](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/contextual.py#L32) | function | — |
| [contextual_representation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/contextual.py#L68) | function | — |
| [pool_token_spans](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/contextual.py#L91) | function | — |

### mari_components.retrieval.contradiction

Sparse embedding operations for efficient contradiction retrieval.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/contradiction.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [hoyer_difference_sparsity](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/contradiction.py#L38) | function | — |
| [SparseContradictionScore](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/contradiction.py#L69) | class | — |
| [sparse_contradiction_score](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/contradiction.py#L78) | function | — |
| [SparseContradictionCandidate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/contradiction.py#L111) | class | — |
| [SparseContradictionHit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/contradiction.py#L120) | class | — |
| [rank_sparse_contradictions](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/contradiction.py#L130) | function | — |
| [sparse_contrastive_losses](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/contradiction.py#L200) | function | — |

### mari_components.retrieval.decisions

Composable filtering and cross-stage candidate decision traces.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/decisions.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [FilterPredicate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/decisions.py#L19) | class | — |
| [FilterDecision](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/decisions.py#L29) | class | — |
| [FilterResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/decisions.py#L36) | class | — |
| [filter_with_reasons](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/decisions.py#L42) | function | — |
| [CandidateDecision](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/decisions.py#L66) | class | — |
| [CandidateHistory](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/decisions.py#L90) | class | [append](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/decisions.py#L93), [for_candidate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/decisions.py#L98) |
| [CandidateHistoryDiagnostics](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/decisions.py#L107) | class | — |
| [diagnose_candidate_history](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/decisions.py#L113) | function | — |
| [decisions_from_filter](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/decisions.py#L160) | function | — |
| [decisions_from_context](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/decisions.py#L179) | function | — |

### mari_components.retrieval.disclosure

Conditional and progressive disclosure over caller-owned knowledge.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/disclosure.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [DisclosureOperator](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/disclosure.py#L12) | class | — |
| [DisclosureCondition](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/disclosure.py#L20) | class | — |
| [DisclosureRule](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/disclosure.py#L31) | class | — |
| [DisclosureDecision](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/disclosure.py#L43) | class | — |
| [evaluate_disclosure](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/disclosure.py#L49) | function | — |
| [DisclosureLevel](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/disclosure.py#L85) | class | — |
| [DisclosureUnit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/disclosure.py#L93) | class | — |
| [DisclosureManifestIssueKind](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/disclosure.py#L114) | class | — |
| [DisclosureManifestIssue](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/disclosure.py#L123) | class | — |
| [ProgressiveDisclosureManifest](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/disclosure.py#L130) | class | — |
| [DisclosureManifestReport](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/disclosure.py#L136) | class | [valid](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/disclosure.py#L141) |
| [DisclosureSelection](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/disclosure.py#L146) | class | — |
| [inspect_disclosure_manifest](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/disclosure.py#L153) | function | — |
| [expand_disclosure](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/disclosure.py#L238) | function | — |

### mari_components.retrieval.fusion

Storage-neutral rank fusion and diversity-aware selection.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/fusion.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [RankContribution](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/fusion.py#L11) | class | — |
| [FusedHit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/fusion.py#L21) | class | — |
| [DiversifiedHit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/fusion.py#L30) | class | — |
| [reciprocal_rank_fusion](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/fusion.py#L39) | function | — |
| [maximal_marginal_relevance](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/fusion.py#L105) | function | — |

### mari_components.retrieval.graph

Deterministic graph propagation and passage projection for retrieval.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/graph.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [GraphHit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/graph.py#L11) | class | — |
| [PageRankResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/graph.py#L17) | class | — |
| [personalized_pagerank](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/graph.py#L23) | function | — |
| [project_graph_scores](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/graph.py#L107) | function | — |

### mari_components.retrieval.index

Immutable in-memory MUVERA index built from arbitrary embedding vectors.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/index.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [MuveraIndex](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/index.py#L24) | class | — |
| [RetrievalHit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/index.py#L62) | class | — |
| [build_index](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/index.py#L68) | function | — |
| [search_index](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/index.py#L121) | function | — |

### mari_components.retrieval.indexes

Dependency-light reference indexes with authorization-aware search.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [IndexHit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L22) | class | — |
| [IndexOperation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L27) | class | — |
| [IndexDelta](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L33) | class | — |
| [BM25TermContribution](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L52) | class | — |
| [BM25Explanation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L60) | class | — |
| [ArtifactIndexHit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L67) | class | — |
| [ArtifactBM25Explanation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L73) | class | — |
| [RevisionIndexHit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L80) | class | — |
| [RevisionBM25Explanation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L86) | class | — |
| [ArtifactIndexDelta](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L93) | class | — |
| [DenseFlatIndex](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L135) | class | [search](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L151) |
| [SparseVectorIndex](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L187) | class | [search](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L210) |
| [BM25Index](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L244) | class | [search](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L287), [explain](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L313), [with_deltas](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L350) |
| [ArtifactBM25Index](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L380) | class | [search](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L406), [explain](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L425), [with_deltas](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L433) |
| [RevisionBM25Index](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L453) | class | [search](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L476), [explain](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L495) |
| [HNSWIndex](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L504) | class | [search](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L566) |
| [IVFPQIndex](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L651) | class | [search](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/indexes.py#L694) |

### mari_components.retrieval.maxsim

Exact late-interaction MaxSim scoring.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/maxsim.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [exact_maxsim](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/maxsim.py#L9) | function | — |

### mari_components.retrieval.muvera

Data-oblivious MUVERA fixed-dimensional encodings.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/muvera.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [FDEConfig](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/muvera.py#L14) | class | [partitions](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/muvera.py#L30), [dimension](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/muvera.py#L34) |
| [projection_parameters](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/muvera.py#L41) | function | — |
| [encode_fde](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/muvera.py#L78) | function | — |

### mari_components.retrieval.polarquant

Deterministic 0.5-bit block-2 PolarQuant encoding for MUVERA FDEs.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/polarquant.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [PolarCodec](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/polarquant.py#L12) | class | — |
| [train_polar](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/polarquant.py#L50) | function | — |
| [encode_polar](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/polarquant.py#L71) | function | — |
| [polar_scores](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/polarquant.py#L98) | function | — |

### mari_components.retrieval.research

Model-neutral execution boundaries derived from retrieval research.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/research.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [hypothetical_document_embedding](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/research.py#L22) | function | — |
| [SummaryTreeNode](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/research.py#L61) | class | — |
| [SummaryTree](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/research.py#L71) | class | — |
| [build_summary_tree](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/research.py#L78) | function | — |
| [CorrectiveAction](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/research.py#L145) | class | — |
| [CorrectiveRetrievalPlan](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/research.py#L154) | class | — |
| [plan_corrective_retrieval](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/research.py#L163) | function | — |
| [ActiveRetrievalQuery](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/research.py#L201) | class | — |
| [plan_active_retrieval](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/research.py#L209) | function | — |
| [TreeWalk](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/research.py#L248) | class | — |
| [walk_summary_tree](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/research.py#L256) | function | — |
| [CompressionSentence](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/research.py#L311) | class | — |
| [CompressionResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/research.py#L321) | class | — |
| [selective_compression](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/research.py#L330) | function | — |

### mari_components.retrieval.serialization

Provisional storage-neutral byte serialization for immutable indexes.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/serialization.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [serialize_index](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/serialization.py#L27) | function | — |
| [deserialize_index](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/serialization.py#L58) | function | — |

### mari_components.retrieval.structure

Section-aware context windows with exact retained spans and provenance.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/structure.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [StructuredContextItem](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/structure.py#L25) | class | — |
| [ContextHit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/structure.py#L48) | class | — |
| [ContextExpansionPolicy](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/structure.py#L59) | class | — |
| [ContextFragment](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/structure.py#L79) | class | — |
| [ExpandedContext](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/structure.py#L88) | class | [page_numbers](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/structure.py#L96) |
| [ContextExpansionResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/structure.py#L105) | class | — |
| [context_items_from_atoms](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/structure.py#L111) | function | — |
| [context_items_from_document](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/structure.py#L127) | function | — |
| [expand_structured_context](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/structure.py#L176) | function | — |

### mari_components.retrieval.sufficiency

Evidence requirements, context sufficiency, and retrieval-gap proposals.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/sufficiency.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [InformationRequirement](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/sufficiency.py#L19) | class | — |
| [RequirementStatus](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/sufficiency.py#L25) | class | — |
| [RequirementAssessment](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/sufficiency.py#L33) | class | — |
| [SufficiencyReport](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/sufficiency.py#L41) | class | [sufficient](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/sufficiency.py#L50) |
| [RetrievalGapQuery](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/sufficiency.py#L59) | class | — |
| [ContextUse](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/sufficiency.py#L66) | class | — |
| [ContextContribution](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/sufficiency.py#L76) | class | — |
| [parse_information_requirements](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/sufficiency.py#L88) | function | — |
| [assess_context_sufficiency](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/sufficiency.py#L128) | function | — |
| [parse_retrieval_gap_queries](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/sufficiency.py#L190) | function | — |
| [evaluate_context_contribution](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/sufficiency.py#L225) | function | — |


## Selectable algorithm additions

### mari_components.algorithms.compression

Source-preserving surprisal selection and byte-stream FastCDC.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/compression.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [TextSpan](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/compression.py#L16) | class | — |
| [SurprisalSelection](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/compression.py#L22) | class | — |
| [select_surprising_words](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/compression.py#L28) | function | — |
| [ByteChunk](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/compression.py#L76) | class | — |
| [fastcdc_chunks](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/compression.py#L81) | function | — |

### mari_components.algorithms.graph_retrieval

Selectable graph retrieval computations from HippoRAG 2, LightRAG, Hindsight, Graphiti, and haiku.rag. See docs/algorithm-choices.md for adaptations.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graph_retrieval.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [SeedWeight](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graph_retrieval.py#L16) | class | [weight](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graph_retrieval.py#L22) |
| [hipporag_seed_weights](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graph_retrieval.py#L26) | function | — |
| [ChunkAllocation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graph_retrieval.py#L82) | class | — |
| [weighted_chunk_polling](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graph_retrieval.py#L88) | function | — |
| [TypedLink](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graph_retrieval.py#L133) | class | — |
| [LinkExpansionScore](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graph_retrieval.py#L141) | class | [score](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graph_retrieval.py#L149) |
| [expand_typed_links](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graph_retrieval.py#L153) | function | — |
| [GraphRerankScore](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graph_retrieval.py#L213) | class | — |
| [rank_graph_distances](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graph_retrieval.py#L219) | function | — |
| [rank_episode_mentions](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graph_retrieval.py#L247) | function | — |
| [UnionCandidate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graph_retrieval.py#L274) | class | [key](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graph_retrieval.py#L287) |
| [UnionScore](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graph_retrieval.py#L292) | class | — |
| [rank_candidate_union](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graph_retrieval.py#L297) | function | — |

### mari_components.algorithms.graphs

Optional solver-backed graph choices over caller-owned IDs and edges.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graphs.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [PrizeForest](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graphs.py#L67) | class | — |
| [prize_collecting_forest](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graphs.py#L76) | function | — |
| [louvain_partition](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graphs.py#L130) | function | — |
| [HierarchicalCommunity](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graphs.py#L151) | class | — |
| [hierarchical_leiden_partition](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graphs.py#L159) | function | — |
| [Condensation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graphs.py#L207) | class | — |
| [condense_graph](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graphs.py#L212) | function | — |
| [transitive_reduction_edges](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graphs.py#L230) | function | — |
| [cohesive_subgraph](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/graphs.py#L241) | function | — |

### mari_components.algorithms.lexical

BM25 family with reference-compatible term formulas and explicit matching.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/lexical.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [BM25Variant](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/lexical.py#L16) | class | — |
| [LexicalTerm](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/lexical.py#L23) | class | — |
| [LexicalScore](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/lexical.py#L31) | class | — |
| [BM25VariantIndex](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/lexical.py#L38) | class | [explain](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/lexical.py#L100), [search](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/lexical.py#L133) |

### mari_components.algorithms.linkage

Dedupe-inspired blocking, active acquisition, clustering and matching choices.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/linkage.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [BlockingPredicate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/linkage.py#L13) | class | — |
| [BlockingSelection](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/linkage.py#L28) | class | — |
| [learn_blocking](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/linkage.py#L38) | function | — |
| [acquire_disagreement](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/linkage.py#L100) | function | — |
| [PairScore](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/linkage.py#L140) | class | — |
| [LinkageCluster](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/linkage.py#L151) | class | — |
| [greedy_matching](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/linkage.py#L156) | function | — |
| [gazette_matching](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/linkage.py#L173) | function | — |
| [centroid_clusters](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/linkage.py#L195) | function | — |

### mari_components.algorithms.memory

Selectable MemoryOS, A-MEM and ACE-inspired pure memory policies.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/memory.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [memory_heat](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/memory.py#L11) | function | — |
| [lfu_evictions](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/memory.py#L35) | function | — |
| [heat_promotions](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/memory.py#L51) | function | — |
| [MemoryNote](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/memory.py#L71) | class | — |
| [NoteUpdate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/memory.py#L80) | class | — |
| [NoteChange](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/memory.py#L89) | class | — |
| [evolve_neighborhood](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/memory.py#L94) | function | — |
| [SkillRecord](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/memory.py#L140) | class | — |
| [SkillFeedback](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/memory.py#L155) | class | — |
| [SkillDecision](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/memory.py#L163) | class | — |
| [SkillReduction](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/memory.py#L171) | class | — |
| [reduce_skill_feedback](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/memory.py#L176) | function | — |

### mari_components.algorithms.search

Bounded DRIFT action search and LightRAG-inspired extraction refinement.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/search.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [DriftQuery](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/search.py#L20) | class | — |
| [DriftResponse](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/search.py#L34) | class | — |
| [DriftAction](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/search.py#L40) | class | — |
| [DriftResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/search.py#L48) | class | — |
| [drift_search](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/search.py#L56) | function | — |
| [RefinementResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/search.py#L129) | class | — |
| [refine_extraction](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/search.py#L136) | function | — |

### mari_components.algorithms.subsets

Set objectives and independently selectable greedy optimizers.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/subsets.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [FacilityLocation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/subsets.py#L38) | class | [evaluate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/subsets.py#L64), [marginal_gain](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/subsets.py#L69) |
| [ProbabilisticSetCover](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/subsets.py#L75) | class | [evaluate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/subsets.py#L97), [marginal_gain](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/subsets.py#L101) |
| [SetCover](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/subsets.py#L107) | class | — |
| [LogDeterminant](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/subsets.py#L117) | class | [evaluate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/subsets.py#L137), [marginal_gain](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/subsets.py#L146) |
| [GreedyMethod](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/subsets.py#L152) | class | — |
| [SelectionStep](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/subsets.py#L160) | class | — |
| [SubsetSelection](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/subsets.py#L168) | class | — |
| [maximize_subset](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/subsets.py#L177) | function | — |

### mari_components.algorithms.temporal

Hindsight-inspired temporal ranking, with caller-supplied dates and scores.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/temporal.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [recency_decay](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/temporal.py#L11) | function | — |
| [dated_recency](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/temporal.py#L34) | function | — |
| [temporal_proof_score](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/temporal.py#L78) | function | — |


## Shared values and contracts

### mari_components.contracts

Backend-neutral boundaries used to compose Mari algorithms.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/contracts.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [Clock](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/contracts.py#L20) | class | — |
| [Authorizer](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/contracts.py#L25) | class | — |
| [Serializer](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/contracts.py#L30) | class | [encode](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/contracts.py#L31), [decode](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/contracts.py#L33) |
| [KnowledgeIndex](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/contracts.py#L37) | class | [search](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/contracts.py#L40) |
| [RevisionResolver](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/contracts.py#L50) | class | — |

### mari_components.errors

Typed failures which hosts can retry, display, or reject explicitly.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/errors.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [ComponentError](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/errors.py#L6) | class | — |
| [AuthenticationFailure](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/errors.py#L10) | class | — |
| [TransientFailure](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/errors.py#L14) | class | — |
| [PermanentFailure](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/errors.py#L22) | class | — |
| [MalformedModelOutput](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/errors.py#L26) | class | — |
| [IncompleteSnapshot](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/errors.py#L30) | class | — |

### mari_components.http

Minimal injected HTTP boundary shared by connector functions.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/http.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [HttpRequest](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/http.py#L42) | class | — |
| [HttpResponse](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/http.py#L67) | class | — |

### mari_components.json

Provider-neutral JSON generation contracts and validation.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/json.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [freeze_json_value](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/json.py#L18) | function | — |
| [freeze_json_mapping](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/json.py#L33) | function | — |
| [canonical_json_bytes](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/json.py#L40) | function | — |
| [to_json_value](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/json.py#L52) | function | — |
| [require_object](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/json.py#L85) | function | — |
| [require_list](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/json.py#L91) | function | — |

### mari_components.references

Structural identities and locators shared across knowledge subsystems.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/references.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [ScopeRef](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/references.py#L10) | class | [key](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/references.py#L25) |
| [ObjectRef](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/references.py#L30) | class | [key](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/references.py#L46) |
| [RevisionRef](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/references.py#L52) | class | [key](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/references.py#L67) |
| [TextSpan](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/references.py#L72) | class | — |
| [JsonPointer](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/references.py#L82) | class | — |
| [RecordField](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/references.py#L91) | class | — |
| [TableCell](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/references.py#L101) | class | — |
| [PageRegion](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/references.py#L111) | class | — |
| [MediaTimeRange](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/references.py#L124) | class | — |
| [LocatedEvidence](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/references.py#L139) | class | — |

### mari_components.schema

Small backend-neutral semantic-schema kernel.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/schema.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [ConceptType](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/schema.py#L14) | class | — |
| [PropertyConstraint](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/schema.py#L23) | class | [constraint_id](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/schema.py#L49) |
| [RelationConstraint](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/schema.py#L54) | class | [constraint_id](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/schema.py#L60) |
| [KnowledgeSchema](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/schema.py#L65) | class | — |
| [SemanticRecord](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/schema.py#L96) | class | — |
| [SemanticRelation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/schema.py#L106) | class | — |
| [SchemaViolation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/schema.py#L114) | class | — |
| [ValidationReport](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/schema.py#L121) | class | — |
| [validate_records](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/schema.py#L126) | function | — |

### mari_components.types

Canonical immutable values shared by Mari Components.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/types.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [canonical_document_id](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/types.py#L18) | function | — |
| [parse_document_id](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/types.py#L26) | function | — |
| [content_revision](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/types.py#L38) | function | — |
| [SyncMode](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/types.py#L45) | class | — |
| [Principal](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/types.py#L51) | class | — |
| [DocumentACL](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/types.py#L63) | class | — |
| [KnowledgeDocument](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/types.py#L82) | class | [document_id](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/types.py#L128), [ref](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/types.py#L132), [ref_in](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/types.py#L138) |
| [KnowledgeSection](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/types.py#L152) | class | — |
| [Tombstone](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/types.py#L173) | class | [document_id](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/types.py#L183) |
| [PollRequest](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/types.py#L188) | class | — |
| [PollPage](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/types.py#L200) | class | — |
| [ChangeHint](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/types.py#L217) | class | — |
| [Evidence](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/types.py#L237) | class | — |
| [FactCandidate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/types.py#L262) | class | — |
| [DecisionCandidate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/types.py#L280) | class | — |
| [GlossaryCandidate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/types.py#L297) | class | — |
| [AnswerCandidate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/types.py#L309) | class | — |


## Source connectors and event handling

### mari_components.connectors.airtable

Airtable base/table snapshot ingestion.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/airtable.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [AirtableConfig](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/airtable.py#L24) | class | — |
| [validate_airtable](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/airtable.py#L35) | function | — |
| [poll_airtable](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/airtable.py#L54) | function | — |

### mari_components.connectors.asana

Asana project/task ingestion with offset checkpoints.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/asana.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [AsanaConfig](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/asana.py#L24) | class | — |
| [validate_asana](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/asana.py#L51) | function | — |
| [poll_asana](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/asana.py#L89) | function | — |

### mari_components.connectors.box

Box folder batch ingestion with marker checkpoints.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/box.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [BoxConfig](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/box.py#L24) | class | — |
| [validate_box](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/box.py#L37) | function | — |
| [poll_box](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/box.py#L56) | function | — |

### mari_components.connectors.catalog

Declarative connector catalog and raw-configuration adapters.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/catalog.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [ConnectorField](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/catalog.py#L65) | class | — |
| [ConnectorDefinition](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/catalog.py#L75) | class | [modes](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/catalog.py#L90), [supports](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/catalog.py#L96), [stream](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/catalog.py#L99), [config](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/catalog.py#L114), [validate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/catalog.py#L117), [poll](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/catalog.py#L125) |
| [connector_definition](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/catalog.py#L587) | function | — |
| [connector_definitions](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/catalog.py#L594) | function | — |

### mari_components.connectors.confluence

Confluence Cloud validation, canonical page fetch, and ordered polling.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/confluence.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [ConfluenceConfig](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/confluence.py#L27) | class | — |
| [storage_to_text](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/confluence.py#L101) | function | — |
| [validate_confluence](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/confluence.py#L144) | function | — |
| [fetch_confluence_page](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/confluence.py#L185) | function | — |
| [poll_confluence](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/confluence.py#L206) | function | — |

### mari_components.connectors.dropbox

Dropbox native delta-cursor ingestion with explicit deleted entries.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/dropbox.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [DropboxConfig](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/dropbox.py#L26) | class | — |
| [validate_dropbox](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/dropbox.py#L51) | function | — |
| [poll_dropbox](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/dropbox.py#L76) | function | — |

### mari_components.connectors.events

Pure verification and bounded change-hint parsing for provider events.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/events.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [parse_json_object](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/events.py#L24) | function | — |
| [verify_hmac_sha256](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/events.py#L36) | function | — |
| [verify_slack_signature](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/events.py#L46) | function | — |
| [github_change_hint](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/events.py#L70) | function | — |
| [confluence_change_hint](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/events.py#L113) | function | — |
| [gdrive_change_hint](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/events.py#L135) | function | — |
| [slack_change_hint](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/events.py#L158) | function | — |
| [gitlab_change_hint](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/events.py#L184) | function | — |
| [box_change_hint](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/events.py#L218) | function | — |
| [microsoft_graph_change_hint](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/events.py#L236) | function | — |
| [object_storage_change_hint](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/events.py#L260) | function | — |
| [cloudevent_change_hint](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/events.py#L316) | function | — |
| [coalesce_hints](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/events.py#L336) | function | — |
| [HintCoalescingReport](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/events.py#L349) | class | — |
| [coalesce_hints_ordered](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/events.py#L357) | function | — |

### mari_components.connectors.filesystem

Stable, bounded local-filesystem batch ingestion.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/filesystem.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [FilesystemConfig](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/filesystem.py#L25) | class | — |
| [validate_filesystem](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/filesystem.py#L37) | function | — |
| [poll_filesystem](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/filesystem.py#L85) | function | — |

### mari_components.connectors.github

GitHub repository, issue/PR, commit, and deletion ingestion.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/github.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [GitHubConfig](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/github.py#L40) | class | — |
| [GitHubCursor](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/github.py#L59) | class | [encode](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/github.py#L64), [decode](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/github.py#L76) |
| [github_source_id](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/github.py#L93) | function | — |
| [validate_github](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/github.py#L127) | function | — |
| [list_github_repositories](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/github.py#L137) | function | — |
| [github_repository](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/github.py#L232) | function | — |
| [validate_github_team](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/github.py#L239) | function | — |
| [github_head](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/github.py#L259) | function | — |
| [github_tree](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/github.py#L272) | function | — |
| [github_blob](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/github.py#L279) | function | — |
| [github_issues](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/github.py#L283) | function | — |
| [github_issue_comments](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/github.py#L299) | function | — |
| [github_pull_request](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/github.py#L312) | function | — |
| [github_pull_files](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/github.py#L324) | function | — |
| [github_commits](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/github.py#L342) | function | — |
| [poll_github](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/github.py#L407) | function | — |

### mari_components.connectors.gitlab

GitLab repository batch ingestion and canonical webhook hints.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/gitlab.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [GitLabConfig](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/gitlab.py#L27) | class | — |
| [gitlab_source_id](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/gitlab.py#L41) | function | — |
| [validate_gitlab](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/gitlab.py#L73) | function | — |
| [poll_gitlab](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/gitlab.py#L105) | function | — |

### mari_components.connectors.google_drive

Google Drive/Docs validation, OAuth refresh, snapshots, and Changes polling.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/google_drive.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [GoogleDriveConfig](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/google_drive.py#L36) | class | — |
| [GoogleOAuthRefresh](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/google_drive.py#L42) | class | — |
| [GoogleDriveWatch](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/google_drive.py#L49) | class | — |
| [start_google_drive_watch](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/google_drive.py#L55) | function | — |
| [refresh_google_access_token](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/google_drive.py#L111) | function | — |
| [validate_google_drive](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/google_drive.py#L156) | function | — |
| [poll_google_drive_changes](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/google_drive.py#L246) | function | — |
| [poll_google_drive](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/google_drive.py#L315) | function | — |

### mari_components.connectors.jira

Jira Cloud issue ingestion with bounded ordered JQL paging.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/jira.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [JiraConfig](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/jira.py#L23) | class | — |
| [validate_jira](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/jira.py#L48) | function | — |
| [poll_jira](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/jira.py#L81) | function | — |

### mari_components.connectors.json_api

Declarative, bounded batch ingestion for JSON REST collections.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/json_api.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [JSONAPIConfig](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/json_api.py#L20) | class | — |
| [poll_json_api](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/json_api.py#L72) | function | — |

### mari_components.connectors.linear

Linear issue/comment ingestion through its GraphQL API.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/linear.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [LinearConfig](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/linear.py#L25) | class | — |
| [validate_linear](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/linear.py#L52) | function | — |
| [poll_linear](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/linear.py#L67) | function | — |

### mari_components.connectors.microsoft_drive

Microsoft Graph delta ingestion for OneDrive and SharePoint document libraries.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/microsoft_drive.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [MicrosoftDriveConfig](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/microsoft_drive.py#L31) | class | — |
| [validate_microsoft_drive](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/microsoft_drive.py#L48) | function | — |
| [poll_microsoft_drive](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/microsoft_drive.py#L71) | function | — |

### mari_components.connectors.notion

Notion page search and bounded block-tree ingestion.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/notion.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [NotionConfig](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/notion.py#L25) | class | — |
| [validate_notion](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/notion.py#L55) | function | — |
| [poll_notion](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/notion.py#L134) | function | — |

### mari_components.connectors.object_storage

SDK-neutral batch ingestion for S3, GCS, Azure Blob, and compatible stores.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/object_storage.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [ObjectStoreConfig](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/object_storage.py#L19) | class | — |
| [SourceObject](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/object_storage.py#L30) | class | — |
| [ObjectListing](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/object_storage.py#L45) | class | — |
| [poll_object_store](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/object_storage.py#L60) | function | — |

### mari_components.connectors.protocol

Connector error and validation functions without runtime orchestration.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/protocol.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [ErrorKind](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/protocol.py#L23) | class | — |
| [ConnectorMode](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/protocol.py#L29) | class | — |
| [connector_configuration_fingerprint](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/protocol.py#L36) | function | — |
| [configured_source_id](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/protocol.py#L42) | function | — |
| [ValidationResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/protocol.py#L56) | class | — |
| [classify_error](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/protocol.py#L62) | function | — |
| [StreamEvent](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/protocol.py#L105) | class | — |
| [PollingConnector](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/protocol.py#L126) | class | — |
| [StreamingConnector](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/protocol.py#L139) | class | — |
| [call_with_retry](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/protocol.py#L151) | function | — |

### mari_components.connectors.rss

Bounded RSS and Atom feed ingestion with conditional batch polling.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/rss.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [RSSConfig](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/rss.py#L23) | class | — |
| [validate_rss](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/rss.py#L86) | function | — |
| [poll_rss](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/rss.py#L99) | function | — |

### mari_components.connectors.singer

Singer/Meltano message adapter for batch connector interoperability.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/singer.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [singer_pages](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/singer.py#L14) | function | — |

### mari_components.connectors.slack

Slack channel/DM history and canonical thread document ingestion.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/slack.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [SlackConfig](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/slack.py#L31) | class | — |
| [validate_slack](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/slack.py#L67) | function | — |
| [fetch_slack_thread](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/slack.py#L211) | function | — |
| [fetch_slack_thread_by_id](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/slack.py#L232) | function | — |
| [poll_slack](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/slack.py#L260) | function | — |

### mari_components.connectors.streaming

Verified event ingestion and canonical refetch for streaming connectors.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/streaming.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [HintHydrationIssue](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/streaming.py#L30) | class | — |
| [HintHydrationReport](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/streaming.py#L37) | class | [valid](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/streaming.py#L43) |
| [validate_hint_hydration](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/streaming.py#L47) | function | — |
| [stream_change_hint](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/streaming.py#L93) | function | — |
| [stream_hints](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/streaming.py#L126) | function | — |
| [stream_pages](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/streaming.py#L147) | function | — |
| [hydrate_hints](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/streaming.py#L172) | function | — |

### mari_components.connectors.trello

Trello board/list/card snapshot ingestion.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/trello.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [TrelloConfig](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/trello.py#L24) | class | — |
| [validate_trello](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/trello.py#L40) | function | — |
| [poll_trello](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/trello.py#L52) | function | — |

### mari_components.connectors.zendesk

Zendesk Guide article ingestion with bounded page checkpoints.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/zendesk.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [ZendeskConfig](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/zendesk.py#L22) | class | — |
| [validate_zendesk](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/zendesk.py#L48) | function | — |
| [poll_zendesk](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/zendesk.py#L64) | function | — |


## Source synchronization

### mari_components.sync.application

Transaction protocol and conformance helper for applying synchronization plans.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/sync/application.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [SyncPlanTransaction](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/sync/application.py#L12) | class | [generation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/sync/application.py#L16), [upsert](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/sync/application.py#L18), [delete](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/sync/application.py#L20), [commit](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/sync/application.py#L22) |
| [apply_sync_plan](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/sync/application.py#L25) | function | — |

### mari_components.sync.planning

Side-effect-free synchronization planning with replay-safe invariants.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/sync/planning.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [ManifestEntry](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/sync/planning.py#L15) | class | — |
| [SyncState](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/sync/planning.py#L23) | class | — |
| [SyncPlan](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/sync/planning.py#L44) | class | — |
| [document_fingerprint](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/sync/planning.py#L54) | function | — |
| [plan_sync](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/sync/planning.py#L72) | function | — |
| [stream_sync](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/sync/planning.py#L191) | function | — |


## Verification and evidence decisions

### mari_components.verification.consensus

Evidence-aware consensus for repeated fact assessments.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/consensus.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [verdict_consensus](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/consensus.py#L13) | function | — |

### mari_components.verification.contradiction

Document-level self-contradiction validation and reward components.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/contradiction.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [reasoning_sentence_references](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/contradiction.py#L22) | function | — |
| [DocumentContradictionAssessment](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/contradiction.py#L47) | class | [reference_coverage](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/contradiction.py#L56) |
| [validate_document_contradiction](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/contradiction.py#L60) | function | — |
| [DocumentContradictionRewards](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/contradiction.py#L92) | class | — |
| [document_contradiction_rewards](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/contradiction.py#L102) | function | — |

### mari_components.verification.models

Immutable results shared by verification algorithms.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/models.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [VerificationScore](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/models.py#L17) | class | — |
| [ScoredAttempt](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/models.py#L40) | class | — |
| [AttemptFailure](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/models.py#L54) | class | — |
| [SelectionResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/models.py#L61) | class | [selected_attempt](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/models.py#L77) |
| [ConsensusResult](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/models.py#L82) | class | — |

### mari_components.verification.portfolio

Bounded, auditable selection over repeated callable results.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/portfolio.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [best_of_n](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/portfolio.py#L15) | function | — |

### mari_components.verification.research

Deterministic controls around model-produced RAG judgments.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/research.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [SelfRagScore](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/research.py#L12) | class | — |
| [score_self_rag_candidate](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/research.py#L23) | function | — |
| [AnswerSource](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/research.py#L70) | class | — |
| [EvidenceNote](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/research.py#L79) | class | — |
| [ChainOfNoteDecision](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/research.py#L88) | class | — |
| [decide_from_evidence_notes](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/research.py#L96) | function | — |

### mari_components.verification.scoring

Deterministic score breakdowns for grounded Mari values.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/scoring.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [harmonic_score](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/scoring.py#L16) | function | — |
| [idea_completeness](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/scoring.py#L23) | function | — |
| [score_grounded](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/scoring.py#L36) | function | — |

### mari_components.verification.selection

Best-of-N selection over candidates produced by any runtime.

[Module source](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/selection.py)

| Public definition | Kind | Public methods declared here |
|---|---|---|
| [numeric_score](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/selection.py#L15) | function | — |
| [select_best](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/selection.py#L26) | function | — |

## Package facades

These modules expose imports or package metadata. Their implementation definitions are indexed at the owning module above.

- [mari_components](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/__init__.py)
- [mari_components.agents](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/agents/__init__.py)
- [mari_components.algorithms](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/algorithms/__init__.py)
- [mari_components.connectors](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/connectors/__init__.py)
- [mari_components.evaluation](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/evaluation/__init__.py)
- [mari_components.graph](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/graph/__init__.py)
- [mari_components.knowledge](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/knowledge/__init__.py)
- [mari_components.platform](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/platform/__init__.py)
- [mari_components.retrieval](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/retrieval/__init__.py)
- [mari_components.sync](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/sync/__init__.py)
- [mari_components.testing](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/testing/__init__.py)
- [mari_components.trajectories](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/trajectories/__init__.py)
- [mari_components.verification](https://github.com/MariHQ/mari-kit/blob/d6f70a0ddaddea45a969bdd1e46148de2a148d09/src/mari_components/verification/__init__.py)

## Generation scope

The index scans every Python source file in `src/mari_components`, including definitions housed in package initializers. Private modules are excluded from the public index: `connectors/_shared.py`.

Maintainers regenerate the Markdown and machine-readable inventory together using `mari-kit-landing/tools/generate_algorithm_inventory.py`. The `--check` option reports stale outputs. Research provenance is maintained in the curated guide instead of inferred from function names.
