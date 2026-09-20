"""Adversarial audit of the evidence-freshness boundary for company brains.

Every test probes a decision that determines whether an evidence-backed artifact
(fact, answer, digest, or reviewed-workflow answer) may be reused after a source
change. The suite asserts the conservative half of the contract: when the
current state is unknown or ambiguous, ``reusable`` must be false.

Probed areas:

- deleted documents,
- section-only changes,
- missing section mappings,
- changed and missing revisions,
- conservative cache reuse and status precedence.
"""

from __future__ import annotations

import pytest

from mari_kit import Evidence, KnowledgeDocument
from mari_kit.knowledge import (
    FreshnessStatus,
    KnowledgeDependency,
    assess_dependencies,
    assess_freshness,
    assess_revision_refs,
    evidence_dependencies,
    impacted_artifacts,
    parse_answer,
    section_revisions,
)
from mari_kit.references import ObjectRef, RevisionRef, ScopeRef

_RUNBOOK_V1 = KnowledgeDocument(
    source_id="docs",
    external_id="runbook",
    title="Runbook",
    body=(
        "# Detection\nOld signal.\n\n"
        "# Mitigation\nRestart the worker.\n\n"
        "# Escalation\nPage the lead.\n"
    ),
    revision="v1",
)

# Only the mitigation section changes; detection and escalation are byte-equal.
_RUNBOOK_V2 = KnowledgeDocument(
    source_id="docs",
    external_id="runbook",
    title="Runbook",
    body=(
        "# Detection\nOld signal.\n\n"
        "# Mitigation\nRestart both workers.\n\n"
        "# Escalation\nPage the lead.\n"
    ),
    revision="v2",
)

# The mitigation section is deleted; the surviving document is a new revision.
_RUNBOOK_V3 = KnowledgeDocument(
    source_id="docs",
    external_id="runbook",
    title="Runbook",
    body="# Detection\nOld signal.\n\n# Escalation\nPage the lead.\n",
    revision="v3",
)


def _section_evidence(
    document: KnowledgeDocument,
    section_id: str,
    quote: str,
) -> Evidence:
    revisions = section_revisions((document,))
    assert revisions[(document.document_id, section_id)]
    body = document.body
    start = body.index(quote)
    return Evidence(
        document_id=document.document_id,
        revision=document.revision,
        quote=quote,
        start=start,
        end=start + len(quote),
        section_id=section_id,
        section_revision=revisions[(document.document_id, section_id)],
    )


def _mitigation_evidence() -> Evidence:
    return _section_evidence(_RUNBOOK_V1, "mitigation", "Restart the worker.")


# ---------------------------------------------------------------------------
# Deleted documents
# ---------------------------------------------------------------------------


def test_deleted_document_is_missing_and_not_reusable():
    dependency = KnowledgeDependency(document_id="docs/runbook", revision="v1")
    report = assess_dependencies((dependency,), {})
    assert report.status is FreshnessStatus.MISSING
    assert report.reusable is False
    assert report.missing_dependency_ids == ("docs/runbook",)
    assert report.changes == ()
    assert report.unversioned_dependency_ids == ()


def test_section_dependency_on_deleted_document_is_missing_not_current():
    evidence = _mitigation_evidence()
    report = assess_freshness(
        (evidence,),
        {},
        current_section_revisions=section_revisions((_RUNBOOK_V2,)),
    )
    assert report.status is FreshnessStatus.MISSING
    assert report.reusable is False
    # The containing document is the missing identity; the section is moot.
    assert "docs/runbook" in report.missing_dependency_ids


def test_current_section_map_cannot_resurrect_a_deleted_document():
    # Even if a (stale) section map still carries the exact section revision,
    # document absence is checked first and wins.
    evidence = _mitigation_evidence()
    current = section_revisions((_RUNBOOK_V1,))
    report = assess_freshness(
        (evidence,),
        {},
        current_section_revisions=current,
    )
    assert report.status is FreshnessStatus.MISSING
    assert report.reusable is False


# ---------------------------------------------------------------------------
# Section-only changes
# ---------------------------------------------------------------------------


def test_section_only_change_invalidates_only_the_edited_dependency():
    evidence = _mitigation_evidence()
    report = assess_freshness(
        (evidence,),
        {_RUNBOOK_V2.document_id: _RUNBOOK_V2.revision},
        current_section_revisions=section_revisions((_RUNBOOK_V2,)),
    )
    assert report.status is FreshnessStatus.STALE
    assert report.reusable is False
    assert len(report.changes) == 1
    change = report.changes[0]
    assert change.section_id == "mitigation"
    assert change.dependency_id == f"{_RUNBOOK_V1.document_id}#mitigation"
    assert change.expected_revision == evidence.section_revision
    assert change.current_revision != evidence.section_revision


def test_unrelated_section_change_reuses_unchanged_section():
    evidence = _section_evidence(_RUNBOOK_V1, "escalation", "Page the lead.")
    report = assess_freshness(
        (evidence,),
        {_RUNBOOK_V2.document_id: _RUNBOOK_V2.revision},
        current_section_revisions=section_revisions((_RUNBOOK_V2,)),
    )
    assert report.status is FreshnessStatus.CURRENT
    assert report.reusable is True
    assert report.changes == ()


def test_document_revision_change_alone_does_not_invalidate_section_dependency():
    # The document revision is v2, the section content is unchanged.
    evidence = _section_evidence(_RUNBOOK_V1, "detection", "Old signal.")
    assert evidence.revision != _RUNBOOK_V2.revision
    report = assess_freshness(
        (evidence,),
        {_RUNBOOK_V2.document_id: _RUNBOOK_V2.revision},
        current_section_revisions=section_revisions((_RUNBOOK_V2,)),
    )
    assert report.reusable is True


# ---------------------------------------------------------------------------
# Missing section mappings
# ---------------------------------------------------------------------------


def test_removed_section_is_missing_even_when_document_is_current():
    evidence = _mitigation_evidence()
    report = assess_freshness(
        (evidence,),
        {_RUNBOOK_V3.document_id: _RUNBOOK_V3.revision},
        current_section_revisions=section_revisions((_RUNBOOK_V3,)),
    )
    assert report.status is FreshnessStatus.MISSING
    assert report.reusable is False
    assert report.missing_dependency_ids == (f"{_RUNBOOK_V1.document_id}#mitigation",)


def test_partial_section_map_missing_this_document_is_missing_not_stale():
    evidence = _mitigation_evidence()
    unrelated = KnowledgeDocument(
        source_id="docs",
        external_id="it-guide",
        title="IT guide",
        body="# Accounts\nProvision on day one.\n",
        revision="it-v1",
    )
    report = assess_freshness(
        (evidence,),
        {_RUNBOOK_V2.document_id: _RUNBOOK_V2.revision},
        current_section_revisions=section_revisions((unrelated,)),
    )
    assert report.status is FreshnessStatus.MISSING
    assert report.reusable is False


def test_absent_section_map_falls_back_to_document_revision():
    evidence = _mitigation_evidence()
    report = assess_freshness(
        (evidence,),
        {_RUNBOOK_V2.document_id: _RUNBOOK_V2.revision},
    )
    assert report.status is FreshnessStatus.STALE
    assert report.reusable is False
    # The fallback comparison is document-level, so it reports no section.
    assert report.changes[0].section_id == ""


def test_section_map_is_authoritative_only_when_supplied():
    # Same evidence: current document revision, no map means stale; a complete
    # map proves the section itself is unchanged and allows reuse.
    evidence = _mitigation_evidence()
    current_revisions = {_RUNBOOK_V1.document_id: _RUNBOOK_V1.revision}
    assert assess_freshness((evidence,), current_revisions).reusable is True
    changed = assess_freshness(
        (evidence,),
        {_RUNBOOK_V2.document_id: _RUNBOOK_V2.revision},
        current_section_revisions=section_revisions((_RUNBOOK_V2,)),
    )
    assert changed.reusable is False


# ---------------------------------------------------------------------------
# Changed and missing revisions
# ---------------------------------------------------------------------------


def test_changed_document_revision_is_stale_with_full_change_details():
    dependency = KnowledgeDependency(document_id="docs/runbook", revision="v1")
    report = assess_dependencies((dependency,), {"docs/runbook": "v2"})
    assert report.status is FreshnessStatus.STALE
    assert report.reusable is False
    assert report.missing_dependency_ids == ()
    change = report.changes[0]
    assert change.document_id == "docs/runbook"
    assert change.expected_revision == "v1"
    assert change.current_revision == "v2"
    assert change.section_id == ""


def test_unversioned_document_revision_is_unversioned_not_reusable():
    dependency = KnowledgeDependency(document_id="docs/runbook", revision="v1")
    report = assess_dependencies((dependency,), {"docs/runbook": ""})
    assert report.status is FreshnessStatus.UNVERSIONED
    assert report.reusable is False
    assert report.unversioned_dependency_ids == ("docs/runbook",)
    assert report.changes == ()


def test_unversioned_section_revision_is_unversioned_not_reusable():
    evidence = _mitigation_evidence()
    current = dict(section_revisions((_RUNBOOK_V2,)))
    current[(_RUNBOOK_V1.document_id, "mitigation")] = ""
    report = assess_freshness(
        (evidence,),
        {_RUNBOOK_V2.document_id: _RUNBOOK_V2.revision},
        current_section_revisions=current,
    )
    assert report.status is FreshnessStatus.UNVERSIONED
    assert report.reusable is False
    assert report.unversioned_dependency_ids == (
        f"{_RUNBOOK_V1.document_id}#mitigation",
    )


def test_status_precedence_is_missing_then_unversioned_then_stale():
    missing = KnowledgeDependency(document_id="gone", revision="v1")
    unversioned = KnowledgeDependency(document_id="blank", revision="v1")
    changed = KnowledgeDependency(document_id="changed", revision="v1")
    current_revisions = {"blank": "", "changed": "v2"}
    report = assess_dependencies((changed, unversioned, missing), current_revisions)
    assert report.status is FreshnessStatus.MISSING
    assert report.missing_dependency_ids == ("gone",)
    assert report.unversioned_dependency_ids == ("blank",)
    assert [row.document_id for row in report.changes] == ["changed"]


def test_missing_dependencies_dominate_reusable_artifact_reports():
    # Two artifacts share a document; one artifact records a second missing
    # document and must not be reused even though its shared section is current.
    shared = KnowledgeDependency(document_id="docs/runbook", revision="v1")
    missing = KnowledgeDependency(document_id="docs/gone", revision="v1")
    impacts = impacted_artifacts(
        {
            "answer:partial": (shared,),
            "answer:full": (shared, missing),
        },
        {"docs/runbook": "v1"},
    )
    assert tuple(impacts) == ("answer:full",)
    assert impacts["answer:full"].status is FreshnessStatus.MISSING


# ---------------------------------------------------------------------------
# Structural references
# ---------------------------------------------------------------------------


def test_assess_revision_refs_reports_missing_object():
    obj = ObjectRef(namespace="document", object_id="runbook")
    expected = RevisionRef(object=obj, revision="v1")
    report = assess_revision_refs((expected,), {})
    assert report.status is FreshnessStatus.MISSING
    assert report.reusable is False
    assert report.missing == (expected,)
    assert report.changes == ()


def test_assess_revision_refs_detects_unit_change_at_same_revision():
    obj = ObjectRef(namespace="document", object_id="runbook")
    expected = RevisionRef(object=obj, revision="v1", unit_id="mitigation")
    current = RevisionRef(object=obj, revision="v1", unit_id="detection")
    report = assess_revision_refs((expected,), {obj: current})
    assert report.status is FreshnessStatus.STALE
    assert report.reusable is False
    assert len(report.changes) == 1
    assert report.changes[0].expected == expected
    assert report.changes[0].current == current


def test_assess_revision_refs_current_requires_revision_and_unit_match():
    obj = ObjectRef(namespace="document", object_id="runbook")
    expected = RevisionRef(object=obj, revision="v1", unit_id="mitigation")
    current = RevisionRef(object=obj, revision="v1", unit_id="mitigation")
    report = assess_revision_refs((expected,), {obj: current})
    assert report.status is FreshnessStatus.CURRENT
    assert report.reusable is True


def test_assess_revision_refs_missing_dominates_changed():
    missing_obj = ObjectRef(namespace="document", object_id="gone")
    changed_obj = ObjectRef(namespace="document", object_id="changed")
    expected_missing = RevisionRef(object=missing_obj, revision="v1")
    expected_changed = RevisionRef(object=changed_obj, revision="v1")
    current_changed = RevisionRef(object=changed_obj, revision="v2")
    report = assess_revision_refs(
        (expected_missing, expected_changed),
        {changed_obj: current_changed},
    )
    assert report.status is FreshnessStatus.MISSING
    assert report.missing == (expected_missing,)
    assert report.changes[0].expected == expected_changed


def test_assess_revision_refs_scope_is_part_of_object_identity():
    unscoped = ObjectRef(namespace="document", object_id="runbook")
    scoped = ObjectRef(
        namespace="document",
        object_id="runbook",
        scope=ScopeRef(tenant="acme"),
    )
    # A same-named object in another scope must not satisfy the dependency.
    scoped_expected = RevisionRef(object=scoped, revision="v1")
    report = assess_revision_refs(
        (scoped_expected,), {unscoped: RevisionRef(object=unscoped, revision="v1")}
    )
    assert report.status is FreshnessStatus.MISSING
    assert report.missing == (scoped_expected,)


# ---------------------------------------------------------------------------
# Evidence dependency extraction
# ---------------------------------------------------------------------------


def test_evidence_dependencies_deduplicates_identical_evidence():
    first = Evidence(document_id="docs/1", revision="v1", quote="same")
    second = Evidence(document_id="docs/1", revision="v1", quote="same")
    assert evidence_dependencies((first, second)) == (
        KnowledgeDependency(document_id="docs/1", revision="v1"),
    )


def test_evidence_dependencies_rejects_conflicting_document_revisions():
    first = Evidence(document_id="docs/1", revision="v1", quote="a")
    second = Evidence(document_id="docs/1", revision="v2", quote="b")
    with pytest.raises(ValueError, match="multiple revisions"):
        evidence_dependencies((first, second))


def test_evidence_dependencies_rejects_conflicting_section_revisions():
    first = Evidence(
        document_id="docs/1",
        revision="v1",
        quote="a",
        section_id="mitigation",
        section_revision="s1",
    )
    second = Evidence(
        document_id="docs/1",
        revision="v1",
        quote="b",
        section_id="mitigation",
        section_revision="s2",
    )
    with pytest.raises(ValueError, match="multiple revisions"):
        evidence_dependencies((first, second))


def test_evidence_dependencies_keeps_section_and_document_rows_distinct():
    document = Evidence(
        document_id="docs/1",
        revision="v1",
        quote="a",
    )
    section = Evidence(
        document_id="docs/1",
        revision="v1",
        quote="b",
        section_id="mitigation",
        section_revision="s1",
    )
    assert evidence_dependencies((document, section)) == (
        KnowledgeDependency(document_id="docs/1", revision="v1"),
        KnowledgeDependency(
            document_id="docs/1",
            revision="v1",
            section_id="mitigation",
            section_revision="s1",
        ),
    )


# ---------------------------------------------------------------------------
# Conservative cache reuse
# ---------------------------------------------------------------------------


def test_impacted_artifacts_returns_only_non_reusable_sorted():
    current_revisions = {"docs/runbook": "v1", "docs/changed": "v2"}
    artifacts = {
        "z-current": (KnowledgeDependency(document_id="docs/runbook", revision="v1"),),
        "a-stale": (KnowledgeDependency(document_id="docs/changed", revision="v1"),),
        "m-missing": (KnowledgeDependency(document_id="docs/gone", revision="v1"),),
    }
    impacts = impacted_artifacts(artifacts, current_revisions)
    assert tuple(impacts) == ("a-stale", "m-missing")
    assert impacts["a-stale"].status is FreshnessStatus.STALE
    assert impacts["m-missing"].status is FreshnessStatus.MISSING
    assert set(impacts) == set(artifacts) - {"z-current"}


def test_artifact_without_recorded_dependencies_is_trivially_reusable():
    assert assess_dependencies((), {}).reusable is True
    assert impacted_artifacts({"empty": ()}, {}) == {}


def test_duplicate_dependencies_do_not_duplicate_change_reports():
    # ``missing_dependency_ids`` and ``unversioned_dependency_ids`` are set-like;
    # ``changes`` must deduplicate exact repeats for the same reason.
    dependency = KnowledgeDependency(document_id="docs/runbook", revision="v1")
    report = assess_dependencies((dependency, dependency), {"docs/runbook": "v2"})
    assert report.status is FreshnessStatus.STALE
    assert len(report.changes) == 1
    assert report.changes[0].document_id == "docs/runbook"


def test_distinct_changes_sharing_a_dependency_id_are_not_collapsed():
    # The same document and section recorded at two revisions yields two
    # genuinely different expectations; deduplication is by exact change, not by
    # dependency ID.
    first = KnowledgeDependency(document_id="docs/runbook", revision="v1")
    second = KnowledgeDependency(document_id="docs/runbook", revision="v2")
    report = assess_dependencies((first, second), {"docs/runbook": "v3"})
    assert report.status is FreshnessStatus.STALE
    assert {
        (row.expected_revision, row.current_revision) for row in report.changes
    } == {("v1", "v3"), ("v2", "v3")}


def test_every_dependency_must_be_current_for_reuse():
    shared = KnowledgeDependency(document_id="docs/runbook", revision="v1")
    changed = KnowledgeDependency(document_id="docs/other", revision="v1")
    report = assess_dependencies(
        (shared, changed),
        {"docs/runbook": "v1", "docs/other": "v2"},
    )
    assert report.reusable is False
    assert [row.document_id for row in report.changes] == ["docs/other"]


def test_child_section_change_does_not_invalidate_parent_slice():
    # Sections are non-overlapping slices that end at the next heading, so a
    # parent slice excludes its descendants. Editing a child must not
    # invalidate a dependency on the parent slice, and must invalidate a
    # dependency on the child itself.
    parent_v1 = KnowledgeDocument(
        source_id="docs",
        external_id="policy",
        title="Policy",
        body="# Policy\nIntro.\n\n## Sub\nSub v1.\n",
        revision="p1",
    )
    parent_v2 = KnowledgeDocument(
        source_id="docs",
        external_id="policy",
        title="Policy",
        body="# Policy\nIntro.\n\n## Sub\nSub v2.\n",
        revision="p2",
    )
    current_revisions = {parent_v2.document_id: parent_v2.revision}
    current_sections = section_revisions((parent_v2,))
    parent_evidence = _section_evidence(parent_v1, "policy", "Intro.")
    parent_report = assess_freshness(
        (parent_evidence,),
        current_revisions,
        current_section_revisions=current_sections,
    )
    assert parent_report.status is FreshnessStatus.CURRENT
    assert parent_report.reusable is True
    child_evidence = _section_evidence(parent_v1, "policy/sub", "Sub v1.")
    child_report = assess_freshness(
        (child_evidence,),
        current_revisions,
        current_section_revisions=current_sections,
    )
    assert child_report.status is FreshnessStatus.STALE
    assert child_report.changes[0].section_id == "policy/sub"


def test_parsed_answer_freshness_through_the_public_boundary():
    answer = parse_answer(
        "How do we mitigate?",
        (_RUNBOOK_V1,),
        {
            "answer": "Restart the worker.",
            "evidence": [
                {
                    "document_id": _RUNBOOK_V1.document_id,
                    "quote": "Restart the worker.",
                }
            ],
        },
    )
    current = assess_freshness(
        answer.evidence,
        {_RUNBOOK_V1.document_id: _RUNBOOK_V1.revision},
        current_section_revisions=section_revisions((_RUNBOOK_V1,)),
    )
    stale = assess_freshness(
        answer.evidence,
        {_RUNBOOK_V2.document_id: _RUNBOOK_V2.revision},
        current_section_revisions=section_revisions((_RUNBOOK_V2,)),
    )
    deleted = assess_freshness(answer.evidence, {})
    assert current.reusable is True
    assert stale.status is FreshnessStatus.STALE
    assert stale.reusable is False
    assert deleted.status is FreshnessStatus.MISSING
