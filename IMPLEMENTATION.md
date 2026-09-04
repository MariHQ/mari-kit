# Mari Kit consolidation worklog

This document tracks the changes required to make Mari Kit a coherent,
backend-agnostic substrate for company knowledge systems. The kernel remains a
collection of contracts, values, algorithms, plans, and conformance suites.
Application runtimes continue to own databases, models, authorization policy,
scheduling, and product behavior.

## Status

| Area | Work | Status |
|---|---|---|
| Identity | Introduce structural scope, object, revision, and unit references | Complete |
| Evidence | Add typed locators and material-resolver validation | Complete |
| Stores | Define protocols, fix space isolation and temporal ordering, add conformance suite | Complete |
| Serialization | Use a strict JSON domain and deterministic canonical encoding | Complete |
| Retrieval | Enforce authorization before approximate and exact scoring | Complete |
| Connectors | Bind configured source instances and content revisions deterministically | Partial |
| Documentation | Add outcome-based paths, maturity labels, and executable examples | Complete |
| Packaging | Separate supported contracts from reference and research surfaces in docs | Complete |
| Quality | Format the tree and run lint, type checking, tests, examples, and docs | Complete |

## Shared dependency investment

### Incremental maintenance algorithms

The shared contracts now have four extensions: selection receipts include
candidate-universe and rule dependencies, `DependencyIndex` maintains a reverse
dependency frontier, `reconcile_groups` records deterministic overlap-based
split/merge lineage, and `DeltaAggregate` supports reversible keyed reducers.
Existing snapshot planning remains the correctness reference. Topology edits
still rebuild the index. Scope, authorization, generation tokens, and atomic
receipt persistence stay explicit host responsibilities.

`examples/quickstarts/knowledge_maintenance.py` composes messages, episode
extraction, topic briefs, vectors, retrieval, and aggregate maintenance. Tests
compare the indexed planner with complete snapshot plans and compare event
sequences with clean materialization of the same graph and identities. Model
callbacks are deterministic fixtures. See `docs/incremental-maintenance.md`.

### Original foundation

The common update algorithm now lives in `mari_components.dependencies`.
Atoms expose exact content/context stamps and occurrence-specific bindings,
while retrieval units and evidence use the same scoped source revision.
Governed artifacts expose versioned computation specifications. Legacy view
refresh delegates change decisions to the shared planner.

Plans distinguish reusable, ready, waiting, and blocked outputs. Only receipts
for completed work release downstream consumers. This allows unchanged output
fingerprints to stop propagation after recomputation. Ordered membership stamps
cover additions, removals, and empty collections. Model/configuration versions
are part of every computation specification.

The dependency integration example and event-sequence tests compare incremental
materializations with clean rebuilds. See `docs/dependency-updates.md` for the
shared contracts, snapshot and persistence requirements, and compatibility
boundaries. Existing specialized freshness and provenance APIs remain supported;
their reference values can enter the planner without a new identity system.

## Conversation knowledge

The independent `mari_components.conversation_knowledge` module adds episode
segmentation, evidence-bound extraction, multivector retrieval facets, scoped
topic histories, and observable trajectory adaptation. Compilation supports
settling windows, revision caches, and explicit call budgets; evidence rendering
fails closed on missing, changed, or unauthorized sources.

See the [integration guide](docs/conversation-knowledge.md) for the extraction
contract, research references, validation coverage, and host responsibilities.
The [example](examples/conversation_knowledge_demo.py) uses a fixture callback,
not a live model. Production integration and semantic benchmarks remain open.

## Compatibility policy

Existing document-specific values remain available while the structural
reference model is adopted. Compatibility adapters must preserve information.
New generic APIs use structural references and typed locators. Removal of old
values requires a later versioned deprecation cycle.

## Completion record

### Identity and immutable values

- `ScopeRef`, `ObjectRef`, and `RevisionRef` provide structural identity.
- `canonical_document_id()` frames source and external IDs with reversible percent
  encoding. `parse_document_id()` supports migration and inspection.
- `KnowledgeDocument` records an exact `content_digest` beside the connector's
  `provider_revision`.
- JSON-shaped metadata and configurations are recursively frozen.
- The identity migration guide explains the document-ID change and dual-read
  rollout for existing stores.

### Evidence and freshness

- `LocatedEvidence` binds a `RevisionRef` to `TextSpan`, `JsonPointer`,
  `RecordField`, `TableCell`, `PageRegion`, or `MediaTimeRange`.
- `validate_located_evidence()` resolves text and structured data through a
  caller-owned material resolver. Spatial and time-based media use an injected
  locator callback.
- `assess_revision_refs()` computes freshness for any referenced object type.
- Existing document evidence remains available during the compatibility cycle.

### Storage and application boundaries

- Runtime-checkable protocols cover stores, indexes, authorization, clocks,
  serializers, and revision resolution.
- `InMemoryArtifactStore` isolates tenant and space keys.
- Point-in-time reads choose the newest visible `recorded_at` value, including
  out-of-order commits.
- `InMemoryDocumentStore` provides a small reference implementation.
- Store, index, authorizer, clock, and serializer conformance helpers are public
  under `mari_components.testing`.

### Retrieval and serialization

- Approximate retrieval filters permitted rows before proxy scoring.
- `RevisionBM25Index` accepts structural references and an explicit allowed set.
- Canonical JSON rejects unsupported values, non-string object keys, and
  non-finite floats. Set encoding has deterministic order.
- Sync, pipeline, projection, portability, and connector fingerprints use the
  same strict encoder.

### Connectors

- GitHub and GitLab derive source IDs from repository identity plus non-secret
  selection configuration.
- Fetched records across the connector set use exact content revisions and retain
  provider revisions separately.
- `configured_source_id()` gives connector authors one stable framing function.
- `connector_configuration_fingerprint()` and `SyncState` bind persisted sync
  progress to the connector's non-secret selection settings.

Remaining connector work needs a compatibility decision. Slack, Notion,
Dropbox, Trello, and similar account-scoped connectors need a caller-supplied
stable source-instance identifier. Adding a required field would break current
config construction. A later version should add the field through a deprecation
cycle, then include it in every source ID and sync-state binding.

### Documentation and examples

- The landing page starts with Company search, Governed knowledge, and Agent
  knowledge.
- Each path is an executable example included directly in its documentation.
- Feature pages carry Core, Supported, Reference, Experimental, Research, or
  Proposed maturity labels.
- Platform contracts, store behavior, typed evidence, revision identity,
  freshness, source identity, and structural retrieval have dedicated pages.
- The public name is Mari Kit. The distribution and import names remain
  `mari-components` and `mari_components`.

### Verification on 2026-09-03

| Check | Result |
|---|---|
| Ruff formatting | 230 files formatted |
| Ruff lint | Passed |
| Pyright | 0 errors, 0 warnings |
| Pytest | 299 passed |
| Executable examples | 36 checks passed |
| Documentation policy tests | 5 passed |
| Sphinx strict build | Passed |

## Follow-up boundaries

The compatibility layer still contains `ArtifactRef`, document `Evidence`, and
string dependency references. A future version can migrate these values after
adapters cover every field without dropping section revision details.

Production database and search adapters remain application-owned. Reference
adapter packages can use the public protocols and conformance suites. They do
not belong in the kernel.

Lifecycle evaluation still needs realistic datasets for ACL revocation, source
configuration changes, partial snapshots, superseded policies, deletion
propagation, and projection rebuild equivalence. The current examples establish
deterministic behavioral checks rather than production-scale corpus results.

## Release record

### Documentation review on 2026-09-04

Reviewed all 74 site pages and the repository integration/design notes. Updated
navigation, shared-reference architecture, executable examples, dependency
handoffs, and implementation limits. Added checks for section navigation,
snippet imports, direct public call signatures, and the architecture example.
Historical proposals now point to current guides.

Read-only live checks found the conversation-knowledge URL serving homepage
HTML. A repository push does not publish this site. The updated strict build
requires a separate authorized upload and CDN invalidation. The publication
record below describes the earlier deployment, not these changes.

The review also confirmed a source limitation: weighted
`shortest_path(max_depth=...)` keeps one cost per node and can miss a valid
shallower route. The path guide documents the limitation. A constrained-path
algorithm fix remains separate from this documentation pass.

### Earlier publication

The implementation was committed to `main` as `d834c47` and pushed to
`MariHQ/mari-kit` on 2026-09-03. The strict Sphinx build was uploaded to the
`kit.mari.guru` S3 bucket in AWS account `386318010728`. CloudFront distribution
`E8QTOGCJZ27MT` completed invalidation `I9Z60DIJ6TJ08I8GKQSCJSY0JU`.

Public HTTP checks returned 200 for the homepage, company-search path, evidence
contracts, and composition-contract pages. Publishing the Python distribution
to PyPI remains a separate package release.
