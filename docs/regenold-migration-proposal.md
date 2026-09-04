# Regenold capabilities worth adapting into Mari Kit

> Historical proposal, retained for rationale. Statements about Mari's limited
> retrieval catalog describe the project at the time of this comparison.
> Weighted rank fusion and additional retrieval paths are now implemented. Use
> [current retrieval docs](../mari-kit-landing/docs/retrieve/index.md) and
> [dependency updates](dependency-updates.md) to plan integrations.

This proposal compares Mari Kit's framework-neutral knowledge package with
`regenold-eu-ai-act-rag`. Regenold is a complete, domain-specific service, so
the useful boundary is its small deterministic policies and evaluation
contracts—not its EU AI Act corpus, routes, or accumulated rule tables.

## Recommended order

### 1. Generic rank fusion

Port the core of `app/engines/hybrid_rrf_retriever.py` as a storage-neutral
`reciprocal_rank_fusion` utility. Mari Kit currently exposes one dense retrieval
path (MUVERA candidate generation followed by exact MaxSim). A generic fusion
primitive would let hosts combine it with lexical search and trusted seed lists
without coupling the package to BM25, a database, or legal citation formats.

Keep weighted ranked lists, per-list deduplication, deterministic tie-breaking,
and the positive smoothing-constant validation. Remove Article/Annex
canonicalization and the legal allowlist. Accept an optional caller-supplied
canonicalizer and eligibility predicate instead.

### 2. Bounded sufficiency and missing-evidence plans

Adapt the contract in `app/engines/sufficient_context.py`: after first-pass
retrieval, compare required anchors/facets with retrieved evidence and return an
auditable verdict plus bounded follow-up queries. This fits Mari Kit better as a
pure `RetrievalGap`/`SufficiencyPlan` value than as an environment-gated engine.

Start with exact missing dependencies supplied by the host and deterministic
multi-part query decomposition. Keep follow-up retrieval additive so it cannot
displace first-pass winners. Do not port Regenold's legal reference parser or
its NLI fallback; the repository's own measured history says neural NLI was
slower and less accurate than lexical scoring.

### 3. Position-swapped pairwise evaluation

Generalize `evals/harness/pairwise_prompts.py` and the agreement logic in
`evals/harness/ab_judge.py`. Mari Kit's current agent evaluation checks tool and
outcome invariants but cannot compare two answer/retrieval policies. A small
framework-neutral evaluator should:

- render one axis per judgment;
- judge A/B and B/A;
- count a preference only when both positions agree;
- retain per-axis reasons and inconclusive outcomes;
- accept an injected JSON generator so providers remain application-owned.

Use product-knowledge axes by default: answer correctness, evidence
faithfulness, completeness, and conciseness. Tone should be an optional
host-defined rubric.

### 4. Safety envelope for post-generation repair

Extract the acceptance policy around Regenold's `verify_and_repair` rather than
its legal citation parser or model prompt. A generic Mari primitive could accept
an original grounded answer and a proposed revision only when configured
invariants hold: non-empty output, bounded shrinkage, no loss of all evidence,
no new unresolved dependencies, and no verifier meta-commentary. On any error,
it returns the original plus a structured reason.

This would support optional faithfulness repair while keeping `parse_answer`
the strict source-of-truth boundary. It should ship only with pairwise
evaluation coverage because a repair pass can improve prose while silently
damaging evidence precision.

### 5. Cache-identity completeness checks

If Mari Kit later gains configurable response caches, adapt the AST-based idea
in `tests/test_r355_cache_key_complete.py`: every response-affecting setting
must appear in cache identity or carry an explicit reason why it is excluded.
This is not needed for the current immutable retrieval index and explicit
workflow cache keys, but it is a valuable regression gate before adding a
runtime engine.

## Do not move

- EU AI Act Article/Annex parsers, legal taxonomies, curated intercepts, or the
  large route post-processing stack: these are product- and corpus-specific.
- Graph-primary retrieval or broad graph expansion: Regenold records that it
  buries operative evidence under generic context.
- Global top-K/reference trimming: Regenold's evaluations found that it drops
  gold evidence.
- Neural NLI verification or heavyweight ML runtime dependencies.
- Regenold's environment-flag architecture. Mari Kit should keep behavior in
  explicit immutable configuration passed by callers.

## Suggested delivery slices

1. Add generic RRF with deterministic unit tests and a MUVERA + lexical example.
2. Add a pure sufficiency-plan type and traceable additive re-retrieval example.
3. Extend agent evaluation with position-swapped pairwise comparison.
4. Evaluate a generic bounded repair envelope against grounded-answer fixtures;
   keep it opt-in until the pairwise gate shows no evidence regression.
