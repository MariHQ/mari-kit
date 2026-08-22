# Mari Kit handoff

## Purpose

Mari Kit is a collection of reusable Python tools for making AI agents more
consistent and correct when they work with a company's knowledge. It must let a
host assemble grounding, evidence, retrieval, review, and learned-workflow
behavior from ordinary functions and small protocols without adopting Mari's
server, UI, database, authentication, scheduler, or deployment model.

The organizing outcome is agent correctness: equivalent questions should use
the same reviewed knowledge and behavior; claims should remain traceable to the
exact source revisions that support them; model and tool behavior should be
observable and reviewable; and cached or distilled behavior should become stale
when its knowledge dependencies change. Connector and knowledge-management
features exist to support that outcome.

The repository was extracted with history from `mari-components` in
`MariHQ/mari`. Mari consumes it as a Git submodule at `vendor/mari-kit`; the
product repository is a consumer and reference implementation, not the source
of reusable behavior.

## Non-negotiable boundary

Public operations follow this shape:

```text
explicit values + explicit dependency callables -> typed values or event stream
```

Library code must not:

- create an application or `KnowledgeBase` object;
- read environment variables or Mari configuration;
- connect to a database, object store, model, or queue implicitly;
- start threads, schedulers, servers, or event loops;
- depend on FastAPI, Strawberry, React, Mari authentication, or Mari tables;
- silently choose a model, storage backend, algorithm, retry policy, or fallback;
- persist model output or connector state on behalf of the caller.

The host owns every side effect. Components expose frozen values, structural
protocols, pure planning functions, and lazy or asynchronous event streams.

## Current contents

The extraction currently publishes eight distributions that share the
`mari_components` import namespace:

- `mari-core`: common values, ACLs, document revisions, audit helpers, HTTP
  request/response values, and errors;
- `mari-connectors`: provider polling, provider event interpretation,
  connector catalog, sync planning, ingestion helpers, and conformance tools;
- `mari-retrieval`: MUVERA, PolarQuant, MaxSim reranking, text chunking,
  immutable in-memory indexes, and serialization;
- `mari-knowledge`: evidence-grounded facts, decisions, answers, glossary,
  summaries, links, review policy, confidence scoring, and document lifecycle;
- `mari-agents`: streaming tool loops, auth requests, observability hooks, and
  deterministic evaluations;
- `mari-trajectories`: event normalization, hierarchical phase analysis,
  workflow mining, matching, and embedding projection;
- `mari-workflows`: storage-neutral workflow lifecycle and step execution;
- `mari-destinations`: MCP lifecycle, knowledge-chat streaming, GitHub comment
  interpretation, and destination helpers.

The executable examples under `examples/` are important acceptance artifacts.
They demonstrate GitHub polling/webhooks, Slack polling/events, Google Drive
changes, knowledge lifecycle functions, and trajectory fast paths.

## Target package map

The next migration should rename `mari-components` concepts into explicit
projects and remove ambiguous ownership:

```text
packages/
  mari-protocols/    dependency-free interoperability values and Protocols
  mari-connectors/   provider-specific polling and canonical change resolution
  mari-sync/         provider-neutral cursor, checkpoint, replay and reconcile logic
  mari-retrieval/    MUVERA, PolarQuant and ranking over caller-supplied vectors
  mari-knowledge/    evidence, facts, answers, decisions, review and lineage rules
  mari-agents/       fully streaming agent/tool execution and evaluation
  mari-workflows/    trajectories, intent clusters, matching, caching and staleness
  mari-adapters/     optional HTTP/model/storage/framework integrations
```

Use independent distributions in this monorepo. Do not split them into separate
Git repositories unless release cadence or ownership actually diverges.

### `mari-protocols`

Split this out of `mari-core`. It owns only dependency-free values such as
documents, revisions, ACLs, principals, upserts, tombstones, change pages,
evidence, model/tool events, embeddings, and structural protocols. Fact,
decision, answer, review, and workflow types belong to their respective
packages. Avoid a generic `core` dumping ground.

### `mari-connectors`

Keep provider knowledge here: GitHub, Slack, Google Drive/Docs, Confluence and
the remaining providers. A connector validates credentials and produces
canonical change pages. Webhook payloads are hints that resolve back to
canonical provider state. Connectors never write application storage or create
embeddings.

Move `sync/planning.py` and `sync/ingestion.py` out of this distribution.

### `mari-sync`

Own cursor advancement, durable page checkpoints, idempotent replay,
incomplete-snapshot safety, tombstones, absence reconciliation, retry
classification, and coalescing. Persistence is supplied by the caller, and a
page's content changes and checkpoint must be committed through one caller-owned
transaction boundary.

### `mari-retrieval`

Keep numerical retrieval code independent of embedding providers and storage.
The public API consumes arrays or embedding values supplied by the caller.
OpenAI, Ollama, S3, filesystems, Postgres, and Iceberg are adapters, not
retrieval primitives.

### `mari-knowledge`

Own the governed knowledge lifecycle: evidence validation, computed confidence,
facts, answers, decisions, glossary, contradictions, review projection,
approval policies, lineage derivation, impact, deprecation, and staleness.
Injected generators may propose structured content; model-reported confidence
is never authoritative. Every artifact retains evidence and source revisions.

### `mari-agents`

Converge the public API on an asynchronous event stream. The host supplies the
model, tools, authorization, cancellation, and observer. The loop must emit
answer deltas and tool lifecycle events immediately and must not buffer a final
answer. Declarative tool authentication requests remain data for the host to
resolve.

### `mari-workflows`

Merge the existing trajectory and workflow packages. A workflow is a reviewed
intent cluster with observations, hierarchical phase/step/substep structure,
tool and document dependencies, cache eligibility, execution decisions, and
staleness—not an automation job. Own cluster matching, merge/split,
distillation, cache validation, and reconciliation planning here.

### `mari-adapters`

Move integration conveniences here or publish them individually when their
dependencies justify it. Candidate adapters include OpenAI-compatible models,
Ollama, OpenTelemetry/OpenInference, Langfuse, MCP, Postgres, Iceberg, FastAPI,
and provider SDK transports. Adapters may depend inward on functional packages;
functional packages never depend on adapters.

## Dependency direction

```text
mari-protocols
  ^-- mari-connectors
  ^-- mari-sync
  ^-- mari-retrieval
  ^-- mari-knowledge
  ^-- mari-agents
  ^-- mari-workflows

mari-adapters -> protocols plus explicitly selected functional packages
Mari server   -> whichever packages and adapters the product composes
```

Prefer protocol-level interoperability over imports between sibling functional
packages. For example, knowledge artifacts refer to protocol evidence values;
they do not import the retrieval implementation.

## Immediate work order

1. Add one root workspace configuration and make every distribution build and
   install independently from a clean environment.
2. Replace the shared `mari_components` namespace with package-owned namespaces
   or a deliberate PEP 420 `mari.*` namespace. Remove accidental cross-wheel
   ownership of the same package directory.
3. Extract `mari-protocols` from `mari-core` and move domain-specific types to
   their owners.
4. Extract `mari-sync` from `mari-connectors`; keep connector functions focused
   on provider I/O and normalization.
5. Merge `mari-trajectories` and `mari-workflows` into the intent-cluster model.
6. Make the agent API asynchronous and streaming end to end while retaining a
   small synchronous adapter if demanded by a real consumer.
7. Move destination-specific delivery into adapters. Keep only reusable MCP
   protocol construction outside the Mari application.
8. Update examples to install published package boundaries rather than relying
   on a repository-wide `PYTHONPATH`.
9. Add release automation, API compatibility checks, package provenance, and
   an Apache-2.0 license declaration to each distribution.
10. Migrate Mari imports one package at a time. Do not add compatibility
    fallbacks; complete each boundary and delete the retired module.

## Acceptance scenarios

The kit is ready for a first public release when clean external projects can:

1. poll and stream GitHub, Slack, Google Drive and Confluence changes into a
   caller-owned store with replay-safe checkpoints and ACLs;
2. embed those changes through an arbitrary HTTP embedder, build MUVERA and
   PolarQuant artifacts, and correctly update or delete derived vectors;
3. extract evidence-grounded facts, answers and decisions and run a human or
   deterministic approval policy without Mari storage;
4. stream an agent turn through arbitrary tools while collecting document and
   tool provenance through an observability hook;
5. cluster collected trajectories, review or split the cluster, mark it
   cacheable, serve an equivalent intent without another model call, and mark
   it stale when a referenced document revision changes;
6. assemble all of the above without importing a server framework, database
   driver, Mari auth, or Mari UI.

Across those scenarios, repeated equivalent agent requests must produce the
same reviewed result while its evidence remains current, and must stop using
that result once a referenced revision changes.

## Relationship to Mari

Mari should import released or vendored Mari Kit packages and implement the
ports with its Postgres/Iceberg repositories, HTTP gateway, project access
context, event inbox, GraphQL/FastAPI surfaces, Slack bot, MCP server, and web
UI. Product-specific presentation, persistence schemas, tenancy, and deployment
remain in Mari.

Do reusable work in this repository first. The Mari repository should contain
only adapter and composition changes needed to consume it.
