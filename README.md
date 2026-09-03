# Mari Components

[![CI](https://github.com/MariHQ/mari-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/MariHQ/mari-kit/actions/workflows/ci.yml)

Composable knowledge-system tools for Python applications and agents.

Mari Components turns changing internal and external documentation into
versioned, evidence-linked knowledge that an application can safely retrieve,
cache, and invalidate. It is one Python distribution and one import package.

Use it with OpenAI Agents SDK, LangGraph, PydanticAI, or any other agent
runtime. Mari Components does not implement an agent loop, model client,
database, scheduler, or authorization system.

Mari also does not define a canonical knowledge graph, ontology, construction
pipeline, query planner, or truth policy. Graph algorithms accept caller-owned
IDs and callbacks and return inspectable values without writing storage. An
application or LLM can compose those operations for its particular system.

## What it provides

- Batch connectors for GitHub, GitLab, Slack, Google Drive, OneDrive,
  SharePoint, Confluence, Dropbox, Box, local files, Notion, RSS/Atom, Airtable, Asana,
  Jira, Linear, Trello, and Zendesk; SDK-neutral S3/GCS/Azure object storage;
  declarative JSON REST; and Singer/Meltano interoperability.
- Checkpoint-free streaming hints for GitHub, GitLab, Slack, Google Drive,
  OneDrive, SharePoint, Confluence, Box, S3, GCS, Azure Blob, and CloudEvents.
- Replay-safe synchronization with canonical document identity, revisions,
  tombstones, checkpoints, and full-snapshot reconciliation.
- Provider-observed ACL metadata and retrieval-time candidate filtering.
- MUVERA candidate generation, PolarQuant compression, and exact MaxSim
  reranking. There is no separate handmade cosine-similarity path.
- Weighted reciprocal-rank fusion, maximal-marginal-relevance diversification,
  and allowed-node Personalized PageRank with passage projection.
- Paper-derived planning boundaries for HyDE, RAPTOR, Self-RAG, CRAG, FLARE,
  A-MEM, Generative Agents, MemWalker, Chain-of-Note, and RECOMP.
- SparseCL contradiction retrieval with Hoyer contrastive-loss conformance,
  cosine candidate generation, sparse reranking, and pre-score authorization;
  plus evidence-localized document self-contradiction validation and RRC rewards.
- Strict parsers for evidence-backed facts, decisions, answers, glossary terms,
  summaries, impact assessments, and refinement proposals.
- Mari-managed tag definitions and assignments that survive provider resyncs.
- Reviewed-intent matching for actual speculative document reads, conservative
  grounded-answer caching, ACL-aware selection, and dependency-impact lookup.
- Stable Markdown section identities and hashes for selective invalidation when
  an unrelated part of a source document changes.
- Stable paragraph, list-item, table-row, and code atoms with Myers/patience
  revision alignment, content-defined fallback spans, temporal versions, and
  exact embedding-reuse and parent-invalidation plans.
- Validated add/update/delete/no-op memory plans and hybrid topic segmentation
  for application-owned online and offline consolidation flows.
- Knowledge-from-experience tools: loaded-revision manifests, expert-feedback
  diagnosis, evidence-bound facts/strategies/pitfalls/constraints, minimal edit
  proposals, dependency validation, and targeted/regression comparisons.
- Knowledge observation ledgers, derivation-loop checks, cross-document edit
  previews and inverses, conditional-disclosure predicates, and progressive
  index-to-source manifests.
- Privacy-bounded OpenAI, Anthropic, and OpenTelemetry evidence adapters;
  direct-follow process models, exact variants, parallel-aware rework,
  reference-path matching, successful-run invariant mining, and sampling.
- Evidence-bound declared, inferred, and hindsight intent candidates with
  caller-owned aggregation, independent-review summaries, and task-adaptive
  rubric validation.
- Framework-neutral context lifecycle hooks around application-owned model and
  tool calls, including explicit scope, purpose, budget, and update events.
- Explicit information requirements, context sufficiency and gap queries,
  context-use and ablation accounting, contextual chunk representations, and
  late-chunk token-span pooling.
- Atom-vector ANN aggregation, contextual multi-vector sections, exact MaxSim,
  existing MUVERA candidate generation, and retrieval-time neighbor expansion.
- Page-aware structured documents with regions, bounding boxes, tables,
  derived representations, and a language-neutral code symbol graph.
- Dependency-free Markdown, HTML, CSV-like, JSON Lines, and Python structure
  parsers with exact source coordinates, partial-result issues, stable
  caller-key identities, table topology, and local call-resolution traces.
- Structural document, region-evidence, schema-drift, scalar-type, and
  stream-hydration validators that report independent violations without
  choosing an acceptance policy.
- Trust-aware write decisions that keep origin, interpretation, taint, scope,
  and provenance separate; plus explainable source-authority resolution.
- Versioned semantic schemas with required-property, cardinality, and
  relation-domain/range validation.
- Scope grants and reviewable cross-scope promotion proposals; dependency-aware
  retention, legal-hold, deletion, and invalidation plans.
- Deterministic, checksum-verified portable knowledge bundles and incremental
  materialized-view refresh plans.
- Paired task-outcome comparisons for success, policy compliance, turns,
  tokens, and tool calls.
- Callback-driven traversal, shortest paths, components, bounded cycle
  enumeration, structural centrality, link scoring, and SimRank.
- Budgeted seed expansion and a transparent prize-guided connected-subgraph
  heuristic, without requiring a graph container.
- Exact graph diffs, structural quality diagnostics, blocking, threshold
  clustering, temporal joins, lineage traversal, and taint propagation.
- Loss-visible GraphML, JSON-LD, NetworkX, RDFLib, and PyTorch Geometric
  conversion helpers using a temporary interchange projection.
- Artifact-neutral evidence with exact visible-context validation, typed hit
  hydration, and multi-budget context selection traces.
- Revision-checked lexical index deltas, injectable analyzers, and per-term BM25
  explanations.
- Evidence-bearing temporal assertions, attribute-aware record diffs,
  explainable blocking and clustering, adjacency projections, and multi-path
  reachability results.
- Reason-preserving filters and candidate histories, diversity-constrained
  context selection, many-to-many graph evidence projection, unique grouped
  interval overlaps, and edge-preserving traversal.
- Artifact-keyed BM25, version-family proposals, grouped coverage metrics,
  weighted contribution traces, uncertainty intervals, and JSON-safe encoding
  for immutable values.

## Installation

The project currently targets Python 3.11 through 3.13.

```bash
python -m pip install 'mari-components @ git+ssh://git@github.com/MariHQ/mari-kit.git'
```

For development:

```bash
git clone git@github.com:MariHQ/mari-kit.git
cd mari-kit
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev,examples]'
```

NumPy is the only required third-party runtime dependency. The `examples`
extra installs the official OpenAI and Slack Python SDKs. The `openai-agents`
and `langchain` extras install those runtimes alongside Mari Components; they
do not replace their native agent APIs with Mari wrappers.

## Core model

A connector emits immutable `KnowledgeDocument` revisions. Provider identity
is namespaced through `document_id`, so IDs from different systems cannot
collide.

```python
from mari_components import DocumentACL, KnowledgeDocument, Principal

document = KnowledgeDocument(
    source_id="github:acme/product",
    external_id="file:docs/refunds.md",
    title="Refund policy",
    body="Enterprise purchases can be refunded within 30 days.",
    revision="8f31c2a",
    source_url="https://github.com/acme/product/blob/main/docs/refunds.md",
    acl=DocumentACL(
        visibility="restricted",
        principals=(Principal(kind="team", identifier="support"),),
    ),
)

assert document.document_id == "github:acme/product/file:docs/refunds.md"
```

`DocumentACL` records what the provider reported. Your application maps those
principals to its users and decides authorization. Mari does not silently turn
provider metadata into an access-control system.

## Synchronization

Connectors yield `PollPage` values. `plan_sync` converts each page into
upserts, deletes, unchanged IDs, and the next durable state without performing
storage writes.

```python
from mari_components import SyncMode
from mari_components.sync import SyncState, plan_sync

state = SyncState()

for page in connector_pages:
    plan = plan_sync(
        state,
        page,
        source_id="github:acme/product",
        mode=SyncMode.FULL,
    )

    # Persist these document changes and plan.state atomically.
    persist(
        upserts=plan.upserts,
        deletes=plan.deletes,
        state=plan.state,
        expected_generation=plan.expected_generation,
    )
    state = plan.state
```

Important guarantees:

- Sync state is bound to one source.
- An incomplete full snapshot cannot resume as an incremental sync.
- Deletion by absence occurs only after a complete full snapshot.
- Explicit provider tombstones are accepted in either mode.
- Every plan advances a generation for compare-and-swap persistence.
- Connector metadata cannot bypass content fingerprinting.

`stream_sync` performs the same planning lazily for an iterable of pages.

## Retrieval with MUVERA

Build an immutable index from one or more vectors per document. Search uses
MUVERA and PolarQuant to select candidates, then exact normalized MaxSim to
rank the final results.

```python
import numpy as np

from mari_components.retrieval import build_index, search_index

index = build_index({
    "docs/refunds": np.asarray([
        [1.0, 0.0, 0.0],
        [0.9, 0.1, 0.0],
    ], dtype=np.float32),
    "docs/deployments": np.asarray([
        [0.0, 1.0, 0.0],
    ], dtype=np.float32),
})

query = np.asarray([[0.95, 0.05, 0.0]], dtype=np.float32)
hits = search_index(
    index,
    query,
    limit=5,
    allowed_document_ids={"docs/refunds"},
)

assert hits[0].document_id == "docs/refunds"
```

`allowed_document_ids` must come from the host's authorization decision. The
filter is applied before candidate scoring and exact reranking, so restricted
documents cannot appear in the result set.

Indexes can be persisted with `serialize_index` and restored with
`deserialize_index`. The serialized files include checksums and reject unknown,
missing, or corrupted entries.

For weighted reciprocal-rank fusion, diversity-aware packing, graph
propagation, topic segmentation, and memory mutation plans, see
[`docs/research-algorithms.md`](docs/research-algorithms.md).
Ten additional paper-derived retrieval, memory, evidence-reading, and
compression boundaries are documented in
[`docs/ten-paper-extensions.md`](docs/ten-paper-extensions.md).
Contradiction retrieval and within-document self-contradiction detection are
documented separately in
[`docs/contradiction-algorithms.md`](docs/contradiction-algorithms.md).
Their permissively licensed cross-implementation checks and the RRC-DSCD
paper/code discrepancy are recorded in
[`docs/contradiction-reference-validation.md`](docs/contradiction-reference-validation.md).
The evidence and validation requirements behind the proposed artifact, store,
pipeline, context, temporal-graph, procedure, and compiler APIs are in
[`docs/proposed-api-foundations.md`](docs/proposed-api-foundations.md).

## Evidence validation and freshness

Mari Components does not own prompts or model calls. Give your agent the source
documents, then pass its structured output to a parser. The parser verifies
document IDs, exact quotes, character spans, and source revisions.

```python
from mari_components.knowledge import assess_freshness, parse_answer

model_output = {
    "answer": "Enterprise purchases can be refunded within 30 days.",
    "disposition": "grounded",
    "evidence": [{
        "document_id": document.document_id,
        "quote": "Enterprise purchases can be refunded within 30 days.",
    }],
}

answer = parse_answer(
    "Can an enterprise purchase be refunded?",
    (document,),
    model_output,
)

current = assess_freshness(
    answer.evidence,
    {document.document_id: "8f31c2a"},
)
assert current.reusable

stale = assess_freshness(
    answer.evidence,
    {document.document_id: "a91de77"},
)
assert not stale.reusable
```

Available parsers include `parse_facts`, `parse_claim_assessments`,
`parse_decisions`, `parse_answer`, `parse_answer_candidates`, `parse_glossary`,
`parse_digest`, `parse_impact`, and `parse_refinement`.

See [`docs/knowledge-parsers.md`](docs/knowledge-parsers.md) for the academic
task foundations behind each parser, the exact contract Mari adopts, and the
places where deterministic validation is intentionally narrower than semantic
entailment or the cited benchmark.

Fact extraction and checking tolerate only recoverable model drift. Cosmetic
claim variants are deduplicated with `normalize_claim`; reordered or lightly
paraphrased assessment rows are restored to the caller's original claim order;
missing rows and unverifiable citations become `uncertain` rather than
invalidating sound findings elsewhere in the batch. Bare evidence quotes are
accepted only when they resolve to exactly one supplied document. Structured
fact fields such as atomic claims, subject/relation/object, scopes, validity,
and conditions are preserved in `FactCandidate.qualifiers`.

Applications can make repeated extraction incremental at section granularity:

```python
from mari_components.knowledge import fact_scan_revisions, pending_fact_sections

pending = pending_fact_sections(
    documents,
    stored_fact_scan_revisions,
    query="retention",
    limit=20,
)
successful = extract_and_persist_review_candidates(pending)
# Commit these checkpoint updates with the candidates when storage permits.
stored_fact_scan_revisions |= fact_scan_revisions(successful)
```

The section revision is a content hash, so unchanged passages remain complete
while an edit creates one new unit of work. Selection is round-robin across
documents. Persist checkpoints only after candidate persistence succeeds,
preferably in the same transaction.

## Verification portfolios

Mari can repeatedly call any candidate-producing function and apply
deterministic, evidence-aware selection. It does not configure or depend on a
model runtime. The result contains the winner plus every score and failed
attempt:

```python
from mari_components.knowledge import parse_claim_assessments
from mari_components.verification import best_of_n, score_grounded


def parse_prediction(prediction):
    return parse_claim_assessments(
        (claim,),
        documents,
        {"assessments": prediction.assessments},
    )[0]


result = best_of_n(
    lambda: generate_assessment(claim, documents),
    parse_prediction,
    score_grounded,
    attempts=3,
    threshold=0.9,
)
assessment = result.selected
score = result.selected_attempt.breakdown
assert score is not None and score.evidence_valid
```

The same package exposes `select_best`, `verdict_consensus`,
`idea_completeness`, and `harmonic_score`. Consensus abstains on ties or weak
agreement and only carries evidence from assessments supporting the winning
verdict. Scores are audit signals, not truth probabilities.

Grounding coverage is a reproducible evidence signal, not a model confidence
score and not an automatic approval decision. Review and publishing policy
remain application concerns.

Evidence parsed from Markdown is bound to a stable heading path and section
content hash. Supply current section revisions to avoid invalidating artifacts
for unrelated edits in the same document:

```python
from mari_components.knowledge import section_revisions

freshness = assess_freshness(
    answer.evidence,
    {current_document.document_id: current_document.revision},
    current_section_revisions=section_revisions((current_document,)),
)
```

If section revisions are omitted, Mari conservatively falls back to the whole
document revision.

## Managed tags

Tags are deliberately separate from connector-owned documents. A new provider
revision therefore cannot erase workspace curation.

```python
from mari_components.knowledge import (
    TagAssignments,
    TagDefinition,
    assign_tags,
    search_weight,
)

definitions = {
    "canonical": TagDefinition(
        key="canonical",
        label="Canonical",
        kind="canonical",
        search_weight=2.0,
        behaviors=("Wins conflicts",),
    ),
}

assignments = assign_tags(
    TagAssignments(),
    document.document_id,
    definitions,
    add=("canonical",),
)

assert assignments.tags_for(document.document_id) == frozenset({"canonical"})
assert search_weight(document.document_id, assignments, definitions) == 2.0
```

Persist `TagDefinition` and `TagAssignments` in application-owned storage. This
matches Mari Cloud's separate tag-definition and document-assignment model.

## Reviewed intents, speculation, and response caching

A `ReviewedWorkflow` is a human-reviewed intent with known read dependencies.
It is not a general workflow engine. The default policy uses different gates
for safe speculative reads and complete cached responses:

- `speculation_threshold=0.70`
- `cache_threshold=0.97`
- `relevant_document_threshold=0.85`

```python
from mari_components.trajectories import (
    WorkflowAction,
    WorkflowPolicy,
    decide_reviewed_workflow,
    start_speculative_retrieval,
)

decision = decide_reviewed_workflow(
    query_vectors,
    reviewed_workflow_index,
    current_revisions,
    current_section_revisions=current_section_revisions,
    allowed_document_ids=authorized_document_ids,
    relevant_document_scores=relevant_document_scores,
    impact_decisions=user_reviewed_impact,
    policy=WorkflowPolicy(),
)

if decision.action is WorkflowAction.CACHED_RESPONSE:
    grounded_answer = decision.cached_answer
    response = grounded_answer.answer

elif decision.action is WorkflowAction.SPECULATIVE_RETRIEVAL:
    retrieval_task = start_speculative_retrieval(
        decision,
        retrieve_documents_async,
    )
    # Continue through the host agent runtime and await/cancel the task there.
```

A complete response is reusable only when:

1. The intent clears the high cache threshold.
2. Every recorded document revision is current.
3. No highly relevant new document has unresolved or positive impact.
4. Every dependency document is authorized for the current user.

When a new highly relevant document appears, a user can mark it non-impacting
and preserve reuse. Otherwise Mari selects speculative retrieval and the host
LLM path. Cached responses are `GroundedAnswer` artifacts, retaining exact
evidence, citations, grounding coverage, and non-factual context dependencies
such as a managed styleguide revision.

Impact analysis is not limited to workflows. Give `impacted_artifacts` a
namespaced mapping of answers, facts, digests, or workflows to their exact
dependencies:

```python
from mari_components.knowledge import impacted_artifacts

impacts = impacted_artifacts(
    {
        "answer:refund-policy": answer.knowledge_dependencies,
        "workflow:support-refund": answer.knowledge_dependencies,
    },
    current_revisions,
    current_section_revisions=current_section_revisions,
)
```

The returned freshness reports identify changed or missing document sections.

## Trajectory analysis

Normalize events emitted by the host agent framework, ask the host model to
label the completed trajectory, and validate that the returned phase ranges
cover the observed events exactly.

```python
from mari_components.trajectories import parse_trajectory_analysis

analysis = parse_trajectory_analysis(
    normalized_events,
    model_labels,
    family_map={"search_product_knowledge": "inspect", "answer": "answer"},
)
```

The library validates labels and redacts common sensitive arguments. It does
not hide a trajectory prompt or execute an agent.

## Connectors

Connector functions accept an injected `HttpTransport`. This keeps network
policy, retries, observability, and testing under application control.

Each catalog provider exposes a configuration value plus validation and batch
polling functions. Providers with event APIs additionally expose verified,
checkpoint-free `ChangeHint` parsing. Events trigger a canonical provider
refetch; they are never treated as complete documents. `stream_pages` can
hydrate hints into `PollPage` values for the same synchronization planner.

See [`docs/connectors.md`](docs/connectors.md) for both contracts, capability
discovery, verification, hydration, and code examples. Executable integrations
are under [`examples/`](examples/).

Credentials are excluded from configuration representations. `HttpRequest`
representations redact authorization headers, bodies, URL userinfo, and common
sensitive query parameters. Applications must still keep raw provider payloads
and tool results out of untrusted logs.

## Executable examples

Every example supports deterministic fixture mode. Together they form a
machine-readable acceptance suite:

- [`github_pipeline`](examples/github_pipeline/) polls repository knowledge,
  processes a webhook hint, repairs a missed event, reconciles deletion, and
  returns evidence-linked output.
- [`slack_event_pipeline`](examples/slack_event_pipeline/) refetches canonical
  thread state, repairs a missed event, and preserves restricted-channel ACLs.
- [`google_drive_change_stream`](examples/google_drive_change_stream/) applies
  edits and deletions while avoiding re-embedding an ACL-only change.
- [`knowledge_lifecycle`](examples/knowledge_lifecycle/) keeps model prompts in
  the application and validates facts, decisions, glossary terms, FAQs, and a
  digest against exact evidence.
- [`slackbot_reliable_answers`](examples/slackbot_reliable_answers/) uses a
  managed styleguide, real speculative retrieval, one DeepSeek answer round,
  one post-answer analysis round, OpenAI embeddings, conservative caching, and
  revision/new-document impact policies.
- [`cross_user_acl_isolation`](examples/cross_user_acl_isolation/) proves that
  restricted documents are excluded before both MUVERA scoring and reviewed
  cache matching for an unauthorized user.
- [`incident_response_drift`](examples/incident_response_drift/) changes one
  section of a GitHub incident runbook, reports every affected answer, digest,
  and workflow, and preserves the cached escalation guidance grounded in an
  unchanged section.
- [`workflow_view_step_cache`](examples/workflow_view_step_cache/) follows
  [WorkflowView](https://arxiv.org/abs/2606.14654) to turn atomic actions into
  detailed phases and a high-level activity, then independently caches the
  evidence-grounded answers discovered inside those phases. It demonstrates
  cross-workflow substep reuse, a tunable cache gate, and selective
  invalidation when one dependency changes.

Run everything without credentials:

```bash
python -m examples.verify_all
pytest -q
```

The Slackbot example can also read real GitHub documents. It posts to Slack
only when `MARI_SLACK_POST=true` is explicitly set. See its
[`README`](examples/slackbot_reliable_answers/README.md) and
[`.env.example`](examples/slackbot_reliable_answers/.env.example).

## Development and release checks

```bash
ruff format --check src tests examples
ruff check src tests examples
pyright src
pytest -q
python -m examples.verify_all
python -m build
```

CI runs those checks on Python 3.11, 3.12, and 3.13 and installs the built wheel
in a clean environment.

## Project status

The API is a pre-release preview. Breaking changes are allowed until the first
stable release and the package is merged back into Mari Cloud. The immediate
integration priorities are transactional sync-state persistence, real
principal-to-document authorization tests, tag-assignment persistence, and
scrubbed fixtures from live connector canaries.

Licensed under the [Apache License 2.0](LICENSE.md).
