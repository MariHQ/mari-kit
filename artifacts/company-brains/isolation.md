> Integration note: this is the original agent report. Findings and intermediate failures below are historical; see [the integrated report](README.md) for final fixes and verification.

# Company Brain Isolation — Build Report

Multi-tenant company brain with identical provider external IDs in distinct
tenants plus per-user authorization, exercised through Mari Kit public APIs.

Owned artifacts (only these were created or changed):

- `examples/company_brains/isolation.py`
- `tests/test_company_brain_isolation.py`
- `artifacts/company-brains/isolation.md`

## Build outcome

Complete and green. `run()` returns a JSON-serializable report with
`isolation_holds: true`, and the module is credential-free and runnable:

```bash
.venv/bin/python -m examples.company_brains.isolation
```

The fixture is two tenants, `tenant-a` and `tenant-b`, each holding a refund
policy and a public status page whose `source_id` (`confluence:acme`) and
`external_id` (`page:refunds`, `page:status`) are identical. Both tenants
therefore produce the same structural `document_id`
(`confluence:acme/page:refunds`), while the contents, revisions, and ACL teams
differ. Users are `alice` (`tenant-a`, `team:finance`), `carol`
(`tenant-a`, no principals, contractor), and `bob` (`tenant-b`, `team:support`).

Isolation is proven along four boundaries:

1. **Scoped stores** — `InMemoryDocumentStore` keyed by `ScopeRef(tenant, space)`
   keeps identical `source_id`/`external_id` revisions separate; an unknown
   tenant scope returns `None`, and `resolve(RevisionRef)` requires the exact
   scoped reference.
2. **Scoped retrieval** — `RevisionBM25Index` is keyed by scoped `RevisionRef`
   values and searched with `allowed_refs`; because the scope is part of
   `RevisionRef.key`, identical external IDs rank independently per tenant.
3. **Per-user authorization** — a host `TenantAuthorizer` implements the public
   `Authorizer` protocol: it denies any `ObjectRef` outside the user's tenant
   before consulting provider ACL metadata, then allows `public` documents or
   documents whose `Principal` set intersects the user's. `carol` never receives
   the restricted tenant-a refund document.
4. **Evidence boundary** — `validate_located_evidence` with scoped
   `visible_refs` rejects a cross-tenant `LocatedEvidence` as `not_visible`,
   while the same evidence is accepted when the host omits `visible_refs`. The
   test suite pins both behaviors so the host contract is explicit.

Scoped artifacts (`KnowledgeArtifact` + `InMemoryArtifactStore`) are likewise
isolated: the same `artifact_id`/`revision` can be committed per tenant,
cross-tenant `get`/`history`/`at_time` return empty, and identical-revision
documents coexist per tenant.

## Host responsibilities (not library bugs)

These are correct-by-design boundaries that the library deliberately leaves to
the host. The report records them because each is a place where a naive host
loses tenant isolation.

- **`allowed_refs` / `allowed_document_ids` are trusted verbatim.** Passing the
  union of two tenants' authorized refs returns both. Mari does not verify an
  authorization decision; the host must derive the set from the authenticated
  user and never from request input. Pinned by
  `test_index_applies_host_supplied_allowed_refs_verbatim`.
- **`visible_refs=None` disables evidence visibility filtering.** With a
  resolver that trusts the reference, cross-tenant evidence is accepted.
  Callers must always pass the authorized scoped set. Pinned by
  `test_missing_visible_refs_admits_cross_tenant_evidence`.
- **The vector index is keyed by bare `document_id`.** Four tenant documents
  collapse to two when the host does not tenant-qualify IDs before
  `build_index`; tenant-qualified keys restore four independent entries. The
  host owns ID namespacing at ingest. Pinned by
  `test_unscoped_vector_index_collapses_identical_document_ids`.
- **The tenant wall is host-owned.** `DocumentACL`/`Principal` record provider
  metadata; Mari does not turn that into authorization. The example enforces it
  structurally in `TenantAuthorizer`, and also only ever considers the user's
  own tenant inventory when computing allow-lists.

## Library API gaps and bugs

No library defect blocked the supported workflow. Three unscoped-evidence
limits are genuine robustness/API gaps and are exposed by tests that pin current
behavior; when the core changes, those tests should be updated deliberately.

1. **Bare-document parsers silently collapse documents that share a
   `document_id`.** `parse_answer` (and `parse_answer_candidates`,
   `parse_facts`, `parse_claim_assessments`) build
   `allowed = {document.document_id: document}`. Two tenants' documents with the
   same `document_id` overwrite each other; no error is raised, and accepted
   evidence depends on iterable order. Exposed by
   `test_parse_answer_silently_collapses_identical_document_ids`: evidence for
   the second tenant is accepted when it is last and rejected when it is first.

   Suggested core fix (in the shared allowance-builder used by the parsers):

   ```python
   allowed: dict[str, KnowledgeDocument] = {}
   for document in documents:
       previous = allowed.get(document.document_id)
       if previous is not None and previous != document:
           raise ValueError(
               f"conflicting documents share document_id "
               f"{document.document_id!r}; namespace or scope documents "
               f"before validation"
           )
       allowed[document.document_id] = document
   ```

   A scope-aware parser overload (accepting scoped `RevisionRef`/`LocatedEvidence`
   like `validate_located_evidence`) would also close the gap without a new error.

2. **`document_evidence_ref` drops scope.** `Evidence` has no scope field, and
   `document_evidence_ref(value)` builds
   `ArtifactRef(namespace="document", ..., scope=None)`. Two tenants with the
   same `document_id` and revision produce equal `ArtifactRef.key` values, so
   `validate_artifact_evidence(..., visible_refs=...)` cannot structurally
   separate them (only quote matching can). Exposed by
   `test_document_evidence_ref_drops_scope`.

   Suggested core fix: add an optional scope and thread it through, e.g.
   `def document_evidence_ref(value: Evidence, *, scope: ScopeRef | None = None)`
   setting `ArtifactRef(..., scope=scope)`, or add `scope: ScopeRef | None` to
   `Evidence` and populate the adapted `ArtifactRef` from it.

3. **`Evidence`-level freshness is not tenant-scoped.** `Evidence`,
   `KnowledgeDependency`, and `assess_freshness`/`evidence_dependencies` key by
   bare `document_id`; `current_revisions` is `Mapping[str, str]`. A caller
   cannot represent both tenants' current revision for a shared `document_id`,
   so one tenant's artifact is always reported stale or missing. Exposed by
   `test_evidence_freshness_dependencies_are_not_tenant_scoped`.

   The scope-preserving alternative already exists: `assess_revision_refs`
   with scoped `RevisionRef`/`ObjectRef`, and scoped `LocatedEvidence`. The fix
   is either to document the requirement that hosts namespace `document_id` per
   tenant, or to add a scoped dependency path alongside the document-id one.

## Commands and results

```text
$ .venv/bin/ruff format --check examples/company_brains/isolation.py tests/test_company_brain_isolation.py
2 files already formatted

$ .venv/bin/ruff check examples/company_brains/isolation.py tests/test_company_brain_isolation.py
All checks passed!

$ .venv/bin/python -m pytest tests/test_company_brain_isolation.py
tests/test_company_brain_isolation.py ....................               [100%]
20 passed in 0.21s

$ .venv/bin/python -m examples.company_brains.isolation
{ ... "isolation_holds": true ... }   # JSON, exit 0
```

Key reported values:

- `document_id_collision`: same id in both tenants, different bodies, distinct
  scoped refs.
- `scoped_store`: tenant-a and tenant-b bodies differ; cross-scope lookup and
  unknown-scope resolution return `None`.
- `retrieval.every_hit_in_user_tenant`: `true`;
  `restricted_refund_hidden_from_contractor`: `true`.
- `vector_index`: `4` documents collapse to `2` unscoped; tenant-qualified
  search returns only tenant-a IDs.
- `evidence_boundary.scoped_evidence_accepted`: `true`;
  `cross_tenant_evidence_rejected`: `true`;
  `missing_visible_refs_admits_cross_tenant`: `true` (host hazard).
- `artifact_store`: tenant-b get/history/at_time empty.
- `host_responsibility_hazards`: all pinned as described above.

## Remaining limitations

- The authorities are reference in-memory stores; production adapters must
  preserve the same scope-key semantics.
- Retrieval is lexical `RevisionBM25Index` plus a trivial stand-in embedding for
  the vector-index collision demonstration. Real embedding quality is out of
  scope and no model or network is used.
- Authorization maps provider principals to users in the host. There is no
  identity provider, session, or audit trail, and no user can span two tenants
  in this fixture.
- Isolation is enforced per operation; there is no transactional guarantee that
  a document commit and its authorization metadata persist atomically. A host
  must ensure user/principal updates and document commits are consistent.
- The cross-tenant evidence/hazard tests pin current unscoped behavior. If the
  core adds scope awareness to `Evidence`/`document_evidence_ref`, the
  corresponding regression tests must be revised to assert the rejected input
  instead.
