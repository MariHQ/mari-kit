> Integration note: this is the original agent report. Findings and intermediate failures below are historical; see [the integrated report](README.md) for final fixes and verification.

# Company Brain: Evidence Freshness Audit

Audit of the evidence-freshness boundary that decides whether a fact, answer,
digest, or reviewed-workflow response may be reused after a source change.

## Scope and ownership

Owned and possibly modified files:

| Artifact | Purpose |
|---|---|
| `src/mari_kit/knowledge/freshness.py` | Unit of code under audit. |
| `tests/test_company_brain_freshness_audit.py` | 31 adversarial tests (new). |
| `artifacts/company-brains/freshness_audit.md` | This report. |

Read for contract and consumer behavior (not modified): `mari_kit/knowledge/`
(`sections.py`, `fact_scans.py`, `answers.py`, `facts.py`), `mari_kit/types.py`,
`mari_kit/references.py`, `mari_kit/trajectories/workflows.py`,
`examples/incident_response_drift/main.py`, `README.md`,
`docs/dependency-updates.md`, `docs/knowledge-parsers.md`, and the existing
freshness tests in `tests/test_knowledge.py`.

The audit treats the documented contract as authoritative: section revisions
are content hashes; a supplied section map is the fine-grained authority; without
one, the whole-document revision is the conservative fallback; `reusable` is
true only for `CURRENT`.

## Result

One concrete reporting defect was found and fixed. No unsafe-reuse defect was
found in any probed area: no scenario was found where `reusable` is true while a
required revision is missing, unversioned, or changed.

### Fixed: duplicate dependencies duplicated `RevisionChange` entries

`assess_dependencies` deduplicated `missing_dependency_ids` and
`unversioned_dependency_ids` with `set(...)` but emitted one `changes` entry per
input occurrence. Passing the same dependency twice therefore produced two
identical `RevisionChange` rows, so a host that counts or enumerates
`report.changes` double-counts the invalidation. The sibling fields already
establish set-like report semantics.

Minimal fix in `src/mari_kit/knowledge/freshness.py`:

```diff
     return FreshnessReport(
         status,
-        tuple(sorted(changes, key=lambda row: row.dependency_id)),
+        tuple(dict.fromkeys(sorted(changes, key=lambda row: row.dependency_id))),
         tuple(sorted(set(missing))),
         tuple(sorted(set(unversioned))),
     )
```

`dict.fromkeys` preserves the existing sorted order and removes only exact
duplicates, so two genuinely different changes that happen to share a
`dependency_id` (for example the same document recorded at two revisions, when
no section map is supplied) are both retained.

Regression tests:

- `test_duplicate_dependencies_do_not_duplicate_change_reports`
- `test_distinct_changes_sharing_a_dependency_id_are_not_collapsed`

`reusable` and the status precedence are unchanged. The fix is one line and does
not touch the host-authorization boundary.

## Probed areas and evidence

| Probe | Expected conservative behavior | Test(s) |
|---|---|---|
| Deleted document | `MISSING`, `reusable=False`; a supplied section map cannot resurrect it | `test_deleted_document_is_missing_and_not_reusable`, `test_section_dependency_on_deleted_document_is_missing_not_current`, `test_current_section_map_cannot_resurrect_a_deleted_document` |
| Section-only change | only the edited section is `STALE`; unrelated/unchanged sections stay `CURRENT` | `test_section_only_change_invalidates_only_the_edited_dependency`, `test_unrelated_section_change_reuses_unchanged_section`, `test_document_revision_change_alone_does_not_invalidate_section_dependency` |
| Missing section mapping | removed section or partial map → `MISSING`, never `CURRENT` | `test_removed_section_is_missing_even_when_document_is_current`, `test_partial_section_map_missing_this_document_is_missing_not_stale` |
| Fallback | no section map → compare the whole-document revision, report document-level change | `test_absent_section_map_falls_back_to_document_revision`, `test_section_map_is_authoritative_only_when_supplied` |
| Changed / missing revisions | changed → `STALE` with full details; empty current → `UNVERSIONED` | `test_changed_document_revision_is_stale_with_full_change_details`, `test_unversioned_document_revision_is_unversioned_not_reusable`, `test_unversioned_section_revision_is_unversioned_not_reusable` |
| Status precedence | `MISSING` > `UNVERSIONED` > `STALE` > `CURRENT` | `test_status_precedence_is_missing_then_unversioned_then_stale`, `test_missing_dependencies_dominate_reusable_artifact_reports` |
| Structural refs | revision or unit mismatch / missing object is not reusable | `test_assess_revision_refs_reports_missing_object`, `test_assess_revision_refs_detects_unit_change_at_same_revision`, `test_assess_revision_refs_current_requires_revision_and_unit_match`, `test_assess_revision_refs_missing_dominates_changed`, `test_assess_revision_refs_scope_is_part_of_object_identity` |
| Evidence extraction | identical evidence deduped; conflicting revisions rejected | `test_evidence_dependencies_deduplicates_identical_evidence`, `test_evidence_dependencies_rejects_conflicting_document_revisions`, `test_evidence_dependencies_rejects_conflicting_section_revisions`, `test_evidence_dependencies_keeps_section_and_document_rows_distinct` |
| Conservative cache reuse | `impacted_artifacts` reports only non-reusable artifacts, sorted; every dependency must be current | `test_impacted_artifacts_returns_only_non_reusable_sorted`, `test_every_dependency_must_be_current_for_reuse`, `test_artifact_without_recorded_dependencies_is_trivially_reusable` |
| End to end | real `parse_answer` evidence flows through the public freshness boundary | `test_parsed_answer_freshness_through_the_public_boundary` |

A randomized differential check (20,000 cases per function, scratch script, not
committed) compared `assess_dependencies` and `assess_revision_refs` against a
per-dependency oracle derived from the docstrings; it found no divergence.

## Behaviors confirmed as intentional (not bugs)

- **A section dependency on a deleted document reports the containing
  `document_id`**, while a removed section of a live document reports the
  `dependency_id`. This asymmetry is already asserted by the onboarding and
  incident brain suites; the section is moot once the document is gone.
- **A parent section slice ends at the next heading and therefore excludes its
  descendants** (`sections.py`). Editing a child does not invalidate a dependency
  on the parent slice, and does invalidate the child dependency. This is
  non-overlapping, content-addressed slicing, and evidence resolution attributes
  each exact quote to exactly one slice.
- **No section map means the document revision is used**, so a section dependency
  can be `STALE` because of an unrelated edit. This is the documented safe
  fallback, not a false positive.
- **Empty dependency sets are trivially reusable.** An artifact that records no
  dependencies has nothing that can go stale; constructing dependencies is the
  caller's responsibility.

## Documented limitation (not changed)

`assess_revision_refs` accepts `Mapping[ObjectRef, RevisionRef]`, so it can hold
only one current `RevisionRef` per object. If an expected set contains several
units (for example multiple atoms or media ranges) of the same object at the same
revision, only the one unit present in `current` is confirmed; the others are
reported `STALE` even though the revision is current. The error direction is
over-invalidation, never silent reuse, so it was left as a documented limitation
rather than a signature-breaking change outside the defect's scope.

## Commands and results

Run from `/Users/henneberger/mari-kit` with the repository virtualenv.

```text
$ .venv/bin/python -m pytest tests/test_company_brain_freshness_audit.py -q
31 passed in 0.07s

$ .venv/bin/python -m pytest tests/test_knowledge.py tests/test_dependency_updates.py \
    tests/test_trajectories_agents.py tests/test_examples.py \
    tests/test_company_brain_onboarding.py tests/test_company_brain_incident.py \
    tests/test_company_brain_search.py -q
96 passed in 0.58s

$ .venv/bin/python -m pytest -q --ignore=tests/test_revision_index_updates.py \
    --ignore=tests/test_company_brain_isolation.py \
    --ignore=tests/test_company_brain_conversation.py
682 passed in 2.64s

$ .venv/bin/ruff check src/mari_kit/knowledge/freshness.py tests/test_company_brain_freshness_audit.py
All checks passed!

$ .venv/bin/ruff format --check src/mari_kit/knowledge/freshness.py tests/test_company_brain_freshness_audit.py
2 files already formatted

$ .venv/bin/pyright src/mari_kit/knowledge/freshness.py tests/test_company_brain_freshness_audit.py
0 errors, 0 warnings, 0 informations
```

## Limitations

- The audit is deterministic and local. No network, model call, or production
  workload was used.
- Three sibling files were mid-edit by concurrent agents during this audit and
  are excluded from the all-suite command because they fail independently of
  freshness: `tests/test_revision_index_updates.py` (collection `ImportError` for
  `RevisionIndexDelta`), `tests/test_company_brain_isolation.py` (2 failures in
  the new `knowledge/_documents.py` `document_lookup`), and
  `tests/test_company_brain_conversation.py` (1 failure in `resolve_evidence`
  ellipsis handling). None of these paths call `assess_dependencies`,
  `assess_freshness`, `assess_revision_refs`, `evidence_dependencies`, or
  `impacted_artifacts`.
- The document-level missing behavior and the `assess_revision_refs` unit
  limitation are recorded rather than changed to avoid breaking concurrently
  authored sibling tests and the public signature.
