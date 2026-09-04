# Native verification algorithms

Mari Kit keeps verification independent of model clients and orchestration
frameworks. Algorithms accept ordinary Python values and callables, and return
immutable results with enough detail for review, storage, and evaluation.

## Included now

### Bounded best-of-N

`best_of_n` calls any candidate-producing function a bounded number of times.
Each result passes through a caller-supplied parser and scorer. Generation,
parsing, and scoring failures are recorded; the first highest-scoring valid
candidate wins. An optional threshold permits early exit.

`select_best` ranks candidates that have already been produced.

These functions do not configure a model, modify sampling parameters, inspect
environment variables, or manage a cache. Repeated calls and their cost are an
explicit application choice.

### Evidence-aware consensus

`verdict_consensus` combines normalized fact assessments with optional weights.
It abstains on ties and weak agreement, and only retains evidence belonging to
the winning verdict.

### Groundedness and completeness

`score_grounded`, `idea_completeness`, and `harmonic_score` provide
deterministic, inspectable metric components. Evidence validity remains a hard
boundary enforced by Mari's parsers; these scores are not truth probabilities.

## Future directions

The following are design ideas, not exports from `mari_components.verification`.
The current [verification page](../mari-kit-landing/docs/govern/verification.md)
documents runnable selection and scoring APIs.

### Native citation normalization

Accept common citation payloads—document IDs or indexes, quotes, offsets,
titles, and URLs—and convert them to `Evidence` only after exact validation
against current documents and revisions. Provider citations remain untrusted
inputs until this boundary succeeds.

### Dataset evaluation

Run a callable over a dataset with deterministic output ordering, bounded
concurrency, per-example metric breakdowns, explicit failures and abstentions,
configuration fingerprints, and JSON/CSV-ready records. Model clients and
cost observations remain injected by the application.

### Multi-candidate comparison

Allow an injected comparator to select or merge already validated candidates
while enforcing invariants: claims cannot change, evidence must still resolve,
and disagreement cannot silently become certainty. Retain the source attempts
and comparison decision.

### Bounded refinement

Represent feedback and acceptance as explicit state transitions. A caller
generates a revised candidate from structured failure information; Mari parses
and scores it with the same rules and only accepts an improvement. No source
inspection or hidden prompt mutation belongs in the algorithm.

### Reviewed-example selection

Use the existing MUVERA/MaxSim retrieval to select similar reviewed examples,
then filter by ACL, freshness, source family, and verdict balance. Persist the
selected IDs as dependencies so edits invalidate stale recipes.

### Offline optimization artifacts

Prompt or demonstration search should consume a versioned recipe, examples,
metric suite, budget, and seed, then emit a versioned artifact containing the
chosen instructions, demonstrations, scores, and provenance. Promotion should
require holdout evaluation and evidence-regression checks.

## Keep out of the core

- model clients, global runtime settings, provider caches, and sampling policy;
- request-time or unbounded prompt optimization;
- framework-specific prediction and document classes;
- majority voting that ignores evidence quality or correlated attempts;
- model confidence treated as truth or exact citation validation;
- hidden mutation of callables, prompts, or process-global configuration.

This leaves room for many algorithms without turning Mari Kit into a model
framework. New strategies should compose around stable data boundaries rather
than introducing a second product or persistence layer.
