# Mari Components

[![CI](https://github.com/MariHQ/mari-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/MariHQ/mari-kit/actions/workflows/ci.yml)

Reliable product knowledge for AI agents.

Mari Components turns changing internal and external documentation into
versioned, evidence-linked knowledge that an application can safely retrieve,
cache, and invalidate. It is one Python distribution and one import package.

Use it with OpenAI Agents SDK, LangGraph, PydanticAI, or any other agent
runtime. Mari Components does not implement an agent loop, model client,
database, scheduler, or authorization system.

## What it provides

- Connectors for GitHub, Slack, Google Drive, Confluence, Dropbox, Notion,
  Airtable, Asana, Jira, Linear, Trello, and Zendesk.
- Replay-safe synchronization with canonical document identity, revisions,
  tombstones, checkpoints, and full-snapshot reconciliation.
- Provider-observed ACL metadata and retrieval-time candidate filtering.
- MUVERA candidate generation, PolarQuant compression, and exact MaxSim
  reranking. There is no separate handmade cosine-similarity path.
- Strict parsers for evidence-backed facts, decisions, answers, glossary terms,
  summaries, impact assessments, and refinement proposals.
- Mari-managed tag definitions and assignments that survive provider resyncs.
- Reviewed-intent matching for actual speculative document reads, conservative
  full-response caching, and dependency-impact lookup.
- Framework-neutral trajectory normalization and model-label validation.

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

Grounding coverage is a reproducible evidence signal, not a model confidence
score and not an automatic approval decision. Review and publishing policy
remain application concerns.

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
    relevant_document_scores=relevant_document_scores,
    impact_decisions=user_reviewed_impact,
    policy=WorkflowPolicy(),
)

if decision.action is WorkflowAction.CACHED_RESPONSE:
    response = decision.cached_answer

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

When a new highly relevant document appears, a user can mark it non-impacting
and preserve reuse. Otherwise Mari selects speculative retrieval and the host
LLM path. `impacted_workflows` finds reviewed intents invalidated by changed or
removed document revisions.

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

Each provider exposes a configuration value plus validation and polling
functions. Priority connectors also expose provider-specific operations such
as Slack thread refetch and Google Drive watches. See the executable projects
under [`examples/`](examples/) for complete integrations.

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
