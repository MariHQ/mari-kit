# Mari Components: scope and extraction plan

Status: proposal for review
Source application reviewed: `/Users/henneberger/mari-cloud`
Proposed package: `mari-components`
Proposed Python import: `mari_components`

## 1. Goal

Mari Components should be the reusable functional core for product-knowledge
systems. It should contain the difficult, generally useful logic Mari has built:

- polling and event interpretation for enterprise knowledge connectors;
- safe incremental synchronization and reconciliation decisions;
- product-knowledge LLM recipes such as fact extraction, fact checking,
  glossary harvesting, FAQ mining, summarization, and link derivation;
- agent trajectory normalization, segmentation, mining, and evaluation;
- MUVERA fixed-dimensional encoding, PolarQuant compression, candidate search,
  and exact MaxSim reranking;
- deterministic review and approval policy functions;
- provider-neutral agent-loop and evaluation helpers where they are genuinely
  independent of Mari's interface.

It should not be a framework. Importing it must not start a server, connect to a
database, create a thread, inspect an environment variable, discover plugins,
or impose an application lifecycle. A caller chooses which functions to call
and owns every side effect.

## 2. The governing boundary

Every public operation follows this shape:

```text
explicit input data + explicit dependency callables -> typed result
```

Examples:

```python
page = poll_confluence(request, state, http=my_http_client)

assessment = check_facts(
    documents,
    generate_json=my_gateway.generate_json,
    policy=my_fact_policy,
)

index = build_muvera(document_vectors, config)
hits = search_muvera(index, query_vectors, limit=20)
```

The package must never silently reach into Mari configuration to locate a
database, model, bucket, project, or current user. It must never silently fall
back to another model or algorithm. If a required dependency is absent or a
model response violates its contract, the function returns a typed failure or
raises a documented package exception. The host application decides whether to
retry, degrade, or fall back.

## 3. What belongs in the package

### 3.1 Shared domain values

Small frozen dataclasses and enums used across components:

- `KnowledgeDocument`, `DocumentRevision`, `DocumentACL`, and `Principal`;
- `Upsert`, `Tombstone`, `ChangeHint`, and `SyncMode`;
- `PollRequest`, `PollPage`, `PollCursor`, and `PageCheckpoint`;
- `Evidence`, `FactCandidate`, `DecisionCandidate`, `GlossaryCandidate`, and
  `AnswerCandidate`;
- `TrajectoryEvent`, `TrajectoryStep`, `TrajectoryPhase`, and
  `TrajectoryAnalysis`;
- `RetrievalHit`, `ReviewItem`, `PolicyDecision`, and typed failure values.

These values describe content and decisions. They do not contain database IDs
as an assumption; identities are opaque strings supplied by the host.

### 3.2 Connector functions

The current provider implementations contain substantial reusable behavior and
should move behind a consistent, page-oriented API:

- Confluence;
- Slack knowledge ingestion;
- Google Drive and Google Docs;
- GitHub repositories, issues, pull requests, and commits;
- Airtable, Asana, Dropbox, Jira, Linear, Notion, Trello, and Zendesk.

`Website` and local `Upload` are deliberately excluded. They were removed from
Mari's connector product and do not belong in the first extraction.

Each connector module should expose ordinary functions, not a class hierarchy
or registry requirement:

```python
def validate_confluence(config, *, http) -> ValidationResult: ...

def poll_confluence(
    config,
    request: PollRequest,
    *,
    http,
) -> Iterator[PollPage]: ...
```

Important behavior preserved and made explicit:

- stable provider identities;
- provider cursors separate from application configuration;
- durable page checkpoints;
- ACL and ACL-only changes;
- explicit tombstones;
- an authoritative `snapshot_complete` flag;
- rate-limit and transient-error classification;
- boundary-safe pagination for equal timestamps;
- deterministic replay and no deletion from an incomplete snapshot.

The package may define an `HttpRequest`/`HttpResponse` value and an injected
`HttpTransport` callable. It should not require Mari's SSRF guard or choose an
HTTP library. Mari will continue injecting its guarded transport; other hosts
can inject theirs.

Provider authentication is connector logic and remains in scope: constructing
OAuth/API requests, refreshing Drive tokens, and verifying provider signatures.
Application authentication is out of scope.

### 3.3 Event-driven connector helpers

Streaming/push integrations should be represented as pure interpretation and
planning functions:

- verify and parse Slack event envelopes;
- determine whether a Slack message is a root mention, DM, or participating
  thread follow-up;
- reduce Slack thread events into canonical conversation/document state;
- verify and parse GitHub deliveries into dirty repository/entity hints;
- verify and parse Confluence webhook events into page/space hints;
- parse Google Drive channel notifications and drain Changes API pages;
- coalesce hints by canonical aggregate key.

These functions return `ChangeHint`, `PollPage`, or outbound request values.
They do not expose FastAPI routes, ACK requests, enqueue jobs, lease work, or
write an inbox. Mari's Postgres event inbox remains the host reliability layer.

The Slack interactive-answer workflow is in scope only as reusable decisions:
routing an event, constructing bounded thread context, constructing an answer
request, and constructing a provider post. Token storage, durable conversation
persistence, and execution remain in Mari.

### 3.4 Synchronization planning

The current sync worker mixes correct reconciliation semantics with Postgres
writes, chunking, embedding, workflow triggers, and UI progress. Split it into a
pure planner:

```python
plan = plan_sync(previous_manifest, poll_page, mode=SyncMode.INCREMENTAL)
# plan.upserts, plan.deletes, plan.next_state, plan.warnings
```

The planner owns invariants, not persistence:

- incomplete snapshots never cause absence deletion;
- incremental absence is never deletion;
- explicit tombstones are authoritative;
- unchanged items retain their prior content;
- an empty changed body replaces stale content;
- cursors only advance with the page/snapshot conditions they describe;
- replaying a page yields the same plan.

Mari applies the plan transactionally, stores checkpoints, chunks text, invokes
an embedder, updates lineage, and publishes progress.

### 3.5 Retrieval: MUVERA and PolarQuant

This is the cleanest first extraction. Move the numerical algorithms from
`server/retrieval.py`:

- `FDEConfig`;
- projection parameter generation;
- MUVERA document/query FDE encoding;
- PolarQuant training and encoding;
- compressed candidate scoring;
- exact MaxSim reranking;
- an in-memory immutable index value and serialization manifest format.

The API consumes NumPy arrays. It has no knowledge of Ollama,
SentenceTransformers, OpenAI, vector databases, S3, filesystems, or Postgres.
Any embedding implementation can be used upstream.

The following remain outside:

- selecting and loading an embedding model;
- embedding text;
- retrieving chunks from a database;
- local/S3 generation publishing and cache refresh;
- per-project index ownership and rebuild scheduling.

Those are host adapters. A later optional `mari-components-io` package could be
considered if several products truly need the same artifact store, but it
should not be part of this package now.

### 3.6 Knowledge extraction and LLM recipes

Extract the reusable recipes currently spread across `mutations_knowledge.py`,
`flowengine.py`, `onboard.py`, `brandimport.py`, and bot code:

- extract fact candidates with evidence;
- check claims against evidence and identify contradictions;
- extract and classify decisions;
- derive explicit and semantic links;
- summarize a knowledge digest;
- assess the impact radius of a changed fact;
- harvest glossary candidates;
- mine FAQ/approved-answer candidates;
- refine or normalize supplied text without becoming a document editor;
- generate grounded answers with citations;
- deterministic automated-approval evaluation.

Each recipe has three layers:

1. a prompt builder producing provider-neutral messages or text;
2. a strict parser/validator producing a typed result;
3. a convenience function accepting an injected `generate` or
   `generate_json` callable.

For example:

```python
result = check_claims(
    claims,
    evidence,
    generate_json=generator,
    limits=FactCheckLimits(max_claims=50, max_evidence_chars=40_000),
)
```

Recipes must carry evidence identifiers through their output so a host can
audit every generated claim. Prompt versions should be named constants included
in results. Output parsing must be strict and independently testable. No recipe
writes facts, tasks, reviews, or audit rows.

### 3.7 Trajectory functions

Move the reusable logic from `server/trajectory.py` while removing its DB,
thread-pool, access-context, and recovery concerns:

- redact/sanitize tool arguments;
- normalize raw events;
- map tools to configurable action families;
- segment coarse-to-fine phases;
- count repeated work and recovery loops;
- build grounded workflow-mining prompts;
- parse each progressive abstraction layer;
- assign a taxonomy from a caller-provided taxonomy;
- produce a complete `TrajectoryAnalysis` value.
- emit agent events through a caller-supplied synchronous observation hook;
- distill repeated analyzed trajectories into argument-free workflow shapes;
- match later intents to those shapes without another model call, so a host can
  explicitly approve and bind a faster execution path.

The core call should be synchronous and explicit:

```python
analysis = analyze_trajectory(
    prompt,
    events,
    generate_json=generator,
    taxonomy=existing_categories,
    family_map=my_tools,
)
```

Mari remains responsible for asynchronously scheduling this call, bounding
concurrency, persisting state, recovering abandoned work, and presenting it.
Observed arguments are never compiled into a workflow or replayed. The host
owns workflow approval, argument binding, authorization, and execution.

### 3.8 Agent helpers and evaluations

Only generic pieces belong here:

- a bounded, provider-neutral tool loop exposed as a lazy event iterator;
- strict tool-call parsing;
- immediate tool-call, tool-result, answer-delta, and completion event values;
- context-size/redaction helpers;
- outcome and tool-use evaluation functions;
- reusable product-knowledge eval cases that do not name Mari routes or labels.

Mari-specific tools (`navigate('/facts')`, GraphQL calls, access checks), screen
guidance, SSE transport, session persistence, and the Mari system prompt stay in
the app. The current `agent_evals.py` cases mostly describe Mari screens, so its
scoring utilities can move but its case catalog should remain in Mari.

The loop does not assemble a final answer or retain emitted events. A host
injects answer streaming and consumes events at its own pace, which gives it
natural backpressure and preserves partial output when a provider disconnects.
The small structured action decision is parsed completely before a tool can run;
provider-specific token transport remains outside this package.

## 4. What explicitly stays in Mari

| Concern | Why it stays in the product |
|---|---|
| FastAPI, GraphQL, and SSE endpoints | Delivery/UI contract |
| Postgres schemas, transactions, leases, and migrations | Host persistence |
| Project access, users, GitHub login, SCIM, API keys | Identity/authorization |
| Secret storage and provider installation ownership | Deployment security |
| Durable event inbox and scheduled execution | Runtime reliability |
| Background workers, retries, concurrency, and observability | Operations |
| SentenceTransformers/Ollama/DeepSeek adapters | Model deployment choice |
| S3/filesystem vector generations | Artifact deployment choice |
| Iceberg canonical storage adapters | Data architecture choice |
| Chunk/document persistence and source records | Product data model |
| Slack/Fly setup routes and public chat destination | Product delivery |
| UI routes, presenter models, wording, and browser tests | Mari experience |
| Review queue projection SQL and mutation application | Mari domain storage |
| Site building and repository audit workspaces | Product features |

## 5. Proposed package layout

```text
mari-components/
  pyproject.toml
  README.md
  LICENSE
  src/mari_components/
    types.py
    errors.py
    http.py
    connectors/
      confluence.py
      slack.py
      google_drive.py
      github.py
      airtable.py
      asana.py
      dropbox.py
      jira.py
      linear.py
      notion.py
      trello.py
      zendesk.py
      events.py
    sync/
      planning.py
      manifests.py
    retrieval/
      muvera.py
      polarquant.py
      maxsim.py
      index.py
      serialization.py
    knowledge/
      facts.py
      decisions.py
      links.py
      glossary.py
      answers.py
      summaries.py
      approvals.py
      prompting.py
    trajectories/
      normalize.py
      segment.py
      mine.py
    agents/
      loop.py
      events.py
      evaluation.py
    testing/
      connector_contract.py
      fakes.py
  tests/
```

This is a source layout, not a runtime architecture. There is no application
object, dependency-injection container, plugin registry, service locator, or
base class users must inherit from.

## 6. Dependencies and packaging

Proposed baseline:

- Python 3.11+;
- `numpy` as the only required runtime dependency, for MUVERA/PolarQuant;
- standard-library dataclasses, typing, JSON, hashing, and URL tools elsewhere.

Connector functions operate through the injected HTTP callable, so `httpx`,
`requests`, and cloud SDKs are not required. Schema validation should initially
use explicit parsing functions and dataclasses rather than importing Mari's
Pydantic dependency. We can add a small dependency only when it materially
improves correctness across multiple components.

SentenceTransformers must not be a dependency, optional extra, or transitive
dependency. Examples can show how to wrap it as an embedder, but the package
only accepts the vectors it produces.

The license needs an explicit decision before code is published. The new
repository should not copy implementation until Mari's applicable source
license and the provenance of the `rt-intent` MUVERA/PolarQuant work are recorded
in `NOTICE`.

## 7. API quality rules

1. **Explicit dependencies.** No global clients, current-user context, config
   reads, or environment-variable reads in component code.
2. **No hidden fallback.** Invalid model output is a typed failure. Callers
   explicitly select retry or deterministic behavior.
3. **Pure by default.** Parsing, planning, ranking, and policy functions are
   deterministic for the same input and seed.
4. **Immutable state.** Connector cursor/checkpoint and index values are returned,
   not mutated in caller configuration dictionaries.
5. **Bounded inputs.** Every network page, prompt, candidate set, and tool loop
   has explicit caller-visible limits.
6. **Evidence survives.** Generated knowledge retains source/revision/span IDs.
7. **Confidence is computed.** Models provide candidate content and citations;
   deterministic code scores validated evidence coverage and corroboration.
8. **Replay is a contract.** Poll pages, event reductions, sync planning, and
   decisions are safe to replay.
9. **Failures are actionable.** Auth, rate-limit, transient, malformed-output,
   incomplete-snapshot, and permanent failures remain distinguishable.
10. **No product strings in core.** No Mari routes, card names, workspace labels,
   or UI copy.
11. **Stable public surface.** Public exports are intentional; internal helpers
    stay underscored. Semantic versioning begins only after Mari consumes the
    extracted package.

## 8. Testing contract

The new repository should have a high-value, reusable test surface rather than
copying every Mari integration test.

### Unit and property tests

- MUVERA candidate recall and exact MaxSim ordering against brute force;
- PolarQuant deterministic encoding, serialization round-trip, corrupt input,
  zero/invalid shapes, and seed reproducibility;
- sync invariants under generated page/replay/delete sequences;
- strict parsing of every LLM recipe;
- prompt snapshots with explicit prompt versions;
- trajectory redaction, phase boundaries, rework, and taxonomy selection;
- event dedupe keys and out-of-order reductions;
- connector cursor boundaries, pagination caps, tombstones, ACL changes,
  malformed responses, and error classification.

### Connector conformance kit

Expose tests downstream connectors can run against their own implementation:

- stable unique IDs;
- no cursor advance beyond incomplete work;
- no absence deletion on incremental/incomplete snapshots;
- explicit delete behavior;
- ACL-only update behavior;
- same-timestamp pagination;
- bounded retry metadata;
- secret redaction in failures;
- crash/replay from each page checkpoint.

### Golden compatibility tests in Mari

Before moving a component, capture representative current inputs and outputs.
During migration, run the old and new implementations side by side and compare:

- connector pages and cursors;
- sync plans;
- retrieval candidate and rerank ordering;
- structured knowledge outputs using fixed fake model responses;
- trajectory normalized steps/phases;
- agent evaluation scoring.

Live SaaS, browser, database, worker, and deployment tests remain in Mari because
they verify integration rather than the component library.

## 9. Migration plan

The deployed product should remain usable after every phase. Do not fork and
maintain two implementations.

### Phase 0: characterize and freeze boundaries

- Add golden fixtures in Mari for the existing algorithms and priority
  connectors (Confluence, Slack, Google Drive, GitHub).
- Record public data shapes and error semantics.
- Resolve package license/provenance.
- Create package CI for Python 3.11, 3.12, and 3.13.

Exit: agreed API examples compile, fixtures cover production-critical behavior,
and no product code has moved.

### Phase 1: extract MUVERA/PolarQuant

- Move pure numerical functions first.
- Create an immutable in-memory index and serialization bytes/manifest API.
- Keep Mari's database rebuild, S3 publishing, generation cache, and embedding
  adapter in `server/retrieval.py` as a thin host adapter.
- Make Mari depend on a pinned local/package revision and run parity tests.

Exit: Mari search uses `mari_components.retrieval`; ranking parity and browser
search/lineage tests pass.

### Phase 2: extract connector contracts and sync planning

- Introduce the new values and injected HTTP boundary.
- Extract reconciliation planning from `connect_sync.py`.
- Adapt Mari persistence around returned plans.
- Publish the connector conformance kit.

Exit: generic sync behavior has no SQL in the package and all existing connector
conformance plus production-like integration tests pass.

### Phase 3: extract the four priority connectors and events

Order: GitHub, Slack, Google Drive, Confluence. For each provider:

1. move provider request/parse/cursor logic;
2. retain a small Mari configuration adapter;
3. run old/new golden parity;
4. run fake-provider fault/replay tests;
5. run a credential-gated live canary before deleting old implementation.

Slack must cover root mention, DM, thread follow-up, event replay, channel ACL,
message edit/delete, and periodic reconciliation. Drive must cover changes token
expiry, tombstones, ACL changes, and watch renewal. GitHub must cover tree
truncation, file deletion, issues/PRs/commits, and webhook reconciliation.
Confluence must cover ordered paging, restrictions, delete/archive, and webhook
refetch.

Exit: Mari imports each provider implementation from the package and contains no
duplicate provider algorithm.

### Phase 4: extract remaining connectors

- Move providers one at a time through the same conformance gate.
- Do not move Website or Upload in this phase.

Exit: the Mari `server/connectors` directory contains adapters only, or is
removed if import compatibility is no longer needed.

### Phase 5: extract knowledge recipes and approval policy

- Split prompt building, strict parsing, and persistence in current mutations.
- Move only prompt/parse/evaluate functions.
- Preserve prompt versions and evidence identities.
- Keep mutation authorization, transactions, review projection, and audit writes
  in Mari.

Exit: fact, decision, glossary, answer, digest, impact, and approval workflows in
Mari call package functions and production behavior is covered by outcome evals.

### Phase 6: extract trajectory and agent helpers

- Move normalization/segmentation/rework first.
- Move LLM mining as an injected synchronous function.
- Keep scheduling, recovery, DB state, and Mari taxonomy records in Mari.
- Move generic eval scoring; retain Mari route cases in Mari.

Exit: trajectory output parity passes, recovery tests remain green, and the
package contains no threads or database imports.

### Phase 7: cleanup and publish

- Delete compatibility re-exports after one release cycle.
- Generate API documentation from public signatures and examples.
- Tag the first version only after Mari consumes every intended component.
- Add an automated check in Mari preventing core modules from importing
  Postgres/FastAPI/auth/UI dependencies.

## 10. Current-code disposition

| Current Mari module | Proposed disposition |
|---|---|
| `connectors/_protocol.py` | Replace with package domain/error/page values |
| `connectors/*.py` | Provider logic moves; Mari configuration adapters remain temporarily |
| `connect_sync.py` | Reconciliation planner moves; SQL/progress/triggers remain |
| `github.py` | Provider client/paging moves; source ownership/job execution remain |
| `provider_events.py` | Signature/event parsing/refetch planning moves; routes/inbox remain |
| `gdrive_events.py` | Notification/change-page logic moves; watches/inbox/DB remain |
| `bots.py` | Slack routing/context/post planning moves; credentials/inbox/DB/answer execution remain |
| `retrieval.py` | Numerical index moves; DB/S3/cache/rebuild scheduling remain |
| `links.py` | Reference parsing/resolution/similarity selection moves; SQL writes remain |
| `mutations_knowledge.py` | Prompt/parse recipes move; mutations, access, SQL, audit remain |
| `flowengine.py` | Reusable step computations may move; scheduler/run persistence stays |
| `review.py` | Policy evaluation moves; projection SQL/application/audit stay |
| `trajectory.py` | Normalize/segment/analyze moves; persistence/workers/recovery stay |
| `agentchat.py` | Generic loop/parser may move; Mari tools/routes/session/access/SSE stay |
| `agent_evals.py` | Scoring utilities move; Mari product case catalog stays |
| `llm.py` | Entirely stays as a Mari model adapter |
| `knowledge_store.py`, `iceberg.py` | Stay as host storage adapters |

## 11. Decisions requested before implementation

1. **Repository/license:** public OSS immediately, or private during extraction?
   Which license should cover the package and the adapted `rt-intent` work?
2. **Python floor:** accept the proposed Python 3.11+, or require 3.12+ to match
   the current server?
3. **Connector breadth:** confirm Website and Upload stay excluded and the other
   ten polling connectors move after the priority four.
4. **Agent scope:** confirm the generic tool loop belongs here, while all Mari
   navigation/setup guidance stays in Mari.
5. **Artifact format:** should the retrieval serialization format be public and
   stable in the first release, or remain provisional until a second consumer
   exists?

## 12. Recommended first reviewable implementation slice

After the decisions above, implement only Phase 1:

- package metadata and CI;
- `retrieval/muvera.py`, `polarquant.py`, `maxsim.py`, and `index.py`;
- exhaustive parity/property tests;
- a thin Mari adapter using externally supplied embeddings;
- no connector, database, workflow, or trajectory changes yet.

That slice validates the package boundary on logic that is already numerical,
valuable, and largely pure. It also avoids combining a repository split with a
simultaneous rewrite of production connector reliability.
