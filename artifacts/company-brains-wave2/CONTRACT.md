# Wave 2 shared contract

Build a host-owned reference application under examples/company_brains/durable.
Mari Kit remains a backend-agnostic library. Use sqlite3 and public Mari APIs.
Other agents own sibling files; do not edit another owner's files or git state.
Use .venv/bin/python and .venv/bin/ruff. Keep code compact and tests behavioral.
Report blockers and proposed fixes in your assigned Markdown report. No skipped
or weakened tests. Do not run the whole suite repeatedly; coordinator integrates.

## store.py (durability builder owns)

SQLiteBrainStore(path), close(), context-manager methods.
state(scope: ScopeRef, source_id: str) -> SyncState (empty if absent).
documents(scope: ScopeRef) -> tuple[KnowledgeDocument,...] in stable order.
get_document(scope, document_id) -> KnowledgeDocument | None.
apply_plan(scope, plan: SyncPlan, *, failpoint: Callable[[str],None] | None=None) -> None.
  One SQLite transaction updates live documents, durable lexical projection,
  and source sync state/generation. Check generation inside BEGIN IMMEDIATE.
  Stage names exactly after_documents, after_projection, before_commit,
  after_commit. A supplied failpoint may os._exit in a child process.
  Same-revision ACL/metadata observations update the live document. History is
  separate from current observations; do not mutate Mari's immutable store API.
  Reject foreign-source changes and generation mismatch before writes.
projection(scope) -> dict[str,str] maps current document_id to body.
set_groups(scope, user_id: str, groups: Iterable[str]) -> None (durable).
groups(scope, user_id) -> frozenset[str].
access_snapshot(scope, user_id) -> tuple[tuple[KnowledgeDocument,...],frozenset[str]]
  Reads live documents and memberships from one consistent SQLite read snapshot.
save_cache(scope, key: str, payload: dict) -> None; load_cache(scope,key) -> dict|None.
JSON serialization must preserve ACL principals, metadata, times, and all sync
state fields. Use Mari json.to_json_value instead of dataclasses.asdict on proxies.
Use bounded busy timeout, explicit rollback, and fresh DB reads across processes.

## engine.py (permission builder owns)

CompanyBrain(store: SQLiteBrainStore, scope: ScopeRef).
search(query: str, *, user_id: str, limit: int=5) -> tuple[KnowledgeDocument,...].
answer(question: str, *, user_id: str, generate=None) -> dict.
  generate(question, documents) -> model-output dict conforming to parse_answer.
  Default is a clearly labeled deterministic extractive answer, with no positive
  hits yielding insufficient_evidence. Output keys: answer (str), disposition
  (str), evidence (JSON list), cache_hit (bool).
  Validate model output via parse_answer; do not allow a callback to cite hidden
  sources. Before serving generated or cached answers, recheck current source
  content and host authorization. Never serve old prose after revoke/delete/edit.
  Cache exact questions and validated dependency fingerprints, using store API.
  Host policy: public and connector_scope docs tenant-visible; restricted docs
  require Principal(kind='team',identifier=<current group>) or matching kind=user.
  Caller provides trusted tenant and user identity; authentication is outside demo.
  Reads authorization from store on every request, not constructor state.

## quality_corpus.py (quality builder owns)

cases() -> list[dict], each includes:
 id, category, question, documents (tuple[KnowledgeDocument,...]),
 expected_disposition ('grounded'|'insufficient_evidence'),
 required_terms (list[str]), forbidden_terms (list[str]),
 allowed_evidence_ids (list[str]).
Categories include current/superseded policy, conflict, ambiguity, missing info,
restricted evidence, irrelevant matches; >=24 cases with varied company domains.
Expected labels are evaluator-only and MUST NOT appear in model prompts.
Prefer extracting stable explicit propositions to grading lexical paraphrases.

## quality_eval.py (quality builder owns)

evaluate_case(case, prediction: dict) -> dict of separate observable metrics;
run(generate=None) -> JSON dict; fixture mode default, live supplied by callback.
Report citation validity, answer correctness proxy, abstention, stale-answer rate
separately with denominators. Invalid output counts as failure, never disappears.
Do not claim deterministic lexical grading proves semantic correctness.

## Scale

benchmarks/company_brain_scale.py standalone CLI, small default and --sizes
1000 10000 25000 (or smaller measured limit), deterministic seed, JSON output.
Use actual durable engine/store once available; separate commit, cold index build,
warm query, ACL filtering, and edit/delete update times. Distinguish wall-time,
Python allocations, and process RSS. Report p50/p95 and corpus/query counts.
No hard latency thresholds in CI. Reference index rebuild is expected; measure it.

## File readiness

Dependencies may not exist initially. Work on independent fixtures/review/tests
first; read the contract for imports. Do not create placeholder modules owned by
another agent. Run dependent tests once files exist; report integration errors
for coordinator. Finish once your owned deliverables and report are complete.
No agents may spawn more agents, install dependencies, read credentials, send
messages, or publish. Only coordinator runs actual model calls and full checks.
