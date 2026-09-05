from dataclasses import replace

import pytest

from mari_components.knowledge import (
    AssetBinding,
    CitationDeclarationStatus,
    CitationEvent,
    CitationEventKind,
    CompactionEvidence,
    CompactionExclusion,
    EvidenceAsset,
    KnowledgeObservation,
    KnowledgeObservationStage,
    OwnedEvidenceRef,
    inspect_citation_declarations,
    plan_evidence_compaction,
    select_evidence_assets,
)
from mari_components.references import LocatedEvidence, ObjectRef, RevisionRef, ScopeRef


def ref(unit="chunk", *, revision="r1", tenant="tenant", document="doc"):
    return RevisionRef(
        object=ObjectRef(
            namespace="docs", object_id=document, scope=ScopeRef(tenant=tenant)
        ),
        revision=revision,
        unit_id=unit,
    )


def owned(owner="search", **kwargs):
    return OwnedEvidenceRef(owner=owner, ref=ref(**kwargs))


def event(identity, ordinal, kind, refs=(), activity="q1", owner="search"):
    return CitationEvent(
        event_id=identity,
        activity_id=activity,
        owner=owner,
        ordinal=ordinal,
        kind=kind,
        refs=refs,
    )


def test_declarations_are_activity_scoped_and_new_outcomes_invalidate_all_owners():
    a, b = owned(), owned("analysis")
    events = [
        event("search", 1, CitationEventKind.OUTCOME, (a,)),
        event("cite", 2, CitationEventKind.DECLARATION, (a,)),
    ]
    assert (
        inspect_citation_declarations(events, activity_id="q1").status
        is CitationDeclarationStatus.DECLARED
    )
    assert (
        inspect_citation_declarations(events, activity_id="q2").status
        is CitationDeclarationStatus.MISSING
    )
    events.append(
        event("analysis", 3, CitationEventKind.OUTCOME, (b,), owner="analysis")
    )
    assert (
        inspect_citation_declarations(events, activity_id="q1").status
        is CitationDeclarationStatus.STALE
    )
    events.append(
        event("same-request", 3, CitationEventKind.DECLARATION, (b,), owner="analysis")
    )
    assert (
        inspect_citation_declarations(events, activity_id="q1").status
        is CitationDeclarationStatus.STALE
    )
    events.append(event("current", 4, CitationEventKind.DECLARATION, (a, b)))
    assert inspect_citation_declarations(reversed(events), activity_id="q1").refs == (
        a,
        b,
    )


def test_empty_declaration_is_explicit_and_does_not_erase_prior_refs():
    a = owned()
    events = [
        event("empty-search", 0, CitationEventKind.OUTCOME),
        event("empty-cite", 1, CitationEventKind.DECLARATION),
    ]
    assert (
        inspect_citation_declarations(events, activity_id="q1").status
        is CitationDeclarationStatus.EMPTY
    )
    events += [
        event("cite", 2, CitationEventKind.DECLARATION, (a,)),
        event("empty-again", 3, CitationEventKind.DECLARATION),
    ]
    report = inspect_citation_declarations(
        events, activity_id="q1", available_evidence=[a]
    )
    assert report.refs == (a,)
    assert report.status is CitationDeclarationStatus.DECLARED
    assert (
        inspect_citation_declarations(events, activity_id="q1").status
        is CitationDeclarationStatus.INVALID
    )
    with pytest.raises(ValueError, match="unique"):
        inspect_citation_declarations([events[0], events[0]], activity_id="q1")


def test_citations_do_not_conflate_owner_revision_or_scope():
    a = owned()
    for other in (owned("analysis"), owned(revision="r2"), owned(tenant="other")):
        events = [
            event("search", 0, CitationEventKind.OUTCOME, (a,)),
            event("cite", 1, CitationEventKind.DECLARATION, (other,)),
        ]
        assert inspect_citation_declarations(events, activity_id="q1").unknown_refs == (
            other,
        )


def observation(activity, artifact, stage, ordinal=0, revision="r1"):
    return KnowledgeObservation(
        observation_id=f"{activity}:{artifact}:{stage.name}:{ordinal}",
        activity_id=activity,
        artifact_id=artifact,
        revision=revision,
        stage=stage,
        ordinal=ordinal,
    )


def record(artifact="a", cost=10, **kwargs):
    return CompactionEvidence(
        artifact_id=artifact,
        evidence=LocatedEvidence(
            ref=ref(artifact, **kwargs), quote=f"source {artifact}"
        ),
        token_count=cost,
    )


def plan(observations, records, budget=None, allowed=None):
    return plan_evidence_compaction(
        observations,
        records,
        activity_order=["old", "recent", "current"],
        current_activity_id="current",
        allowed_evidence_refs=[r.evidence.ref for r in records]
        if allowed is None
        else allowed,
        allowed_asset_refs=(),
        token_budget=budget,
    )


def test_compaction_keeps_whole_cited_evidence_newest_first_and_protects_current():
    records = [record("a"), record("b"), record("c"), record("active")]
    cited, retrieved = (
        KnowledgeObservationStage.CITED,
        KnowledgeObservationStage.RETRIEVED,
    )
    observations = [
        observation("old", "a", cited),
        observation("recent", "a", cited),
        observation("old", "b", cited),
        observation("recent", "c", retrieved),
        observation("old", "active", cited),
        observation("current", "active", retrieved),
    ]
    result = plan(observations, records, 10)
    assert [
        (g.activity_id, [r.artifact_id for r in g.evidence]) for g in result.groups
    ] == [("recent", ["a"])]
    reasons = {t.artifact_id: t.reason for t in result.trace}
    assert reasons == {
        "a": None,
        "b": CompactionExclusion.BUDGET,
        "c": CompactionExclusion.NOT_CITED,
        "active": CompactionExclusion.CURRENT_ACTIVITY,
    }
    assert result.token_count == 10
    assert result.protected_observation_ids == (observations[-1].observation_id,)
    assert observations[-1].observation_id not in result.compact_observation_ids
    assert plan(observations, records).token_count == 20


def test_compaction_fails_on_missing_citations_and_ambiguous_ids_and_excludes_revoked():
    rows = [observation("old", "a", KnowledgeObservationStage.CITED)]
    with pytest.raises(ValueError, match="canonical"):
        plan(rows, [])
    with pytest.raises(ValueError, match="ambiguous"):
        plan(rows, [record(), record(tenant="other")])
    result = plan(rows, [record()], allowed=[])
    assert result.groups == ()
    assert result.trace[0].reason is CompactionExclusion.UNAVAILABLE
    # A permission for a newer revision cannot authorize retained older text.
    assert plan(rows, [record()], allowed=[ref("a", revision="r2")]).groups == ()


def test_asset_selection_deduplicates_full_identity_and_drops_clipped_evidence():
    a, b = ref("a"), ref("b")
    asset = EvidenceAsset(
        ref=ref("#/pictures/0"),
        media_type="image/jpeg",
        captions=("source caption",),
        description="generated",
        description_model="model",
    )
    bindings = [
        AssetBinding(evidence=a, asset=asset),
        AssetBinding(evidence=b, asset=asset),
    ]
    selected = select_evidence_assets(
        bindings,
        retained_evidence=[LocatedEvidence(ref=a)],
        allowed_asset_refs=[asset.ref],
    )
    assert selected.assets[0].evidence_refs == (a,)
    assert selected.assets[0].asset.media_type == "image/jpeg"
    assert selected.assets[0].origin == "retrieved_evidence"
    assert (
        select_evidence_assets(
            bindings, retained_evidence=[], allowed_asset_refs=[asset.ref]
        ).assets
        == ()
    )
    assert (
        select_evidence_assets(
            bindings,
            retained_evidence=[LocatedEvidence(ref=a)],
            allowed_asset_refs=[asset.ref],
            already_attached=[asset.ref],
        ).assets
        == ()
    )
    with pytest.raises(ValueError, match="conflicting"):
        select_evidence_assets(
            [
                bindings[0],
                AssetBinding(evidence=a, asset=replace(asset, captions=("conflict",))),
            ],
            retained_evidence=[LocatedEvidence(ref=a)],
            allowed_asset_refs=[asset.ref],
        )
    other = EvidenceAsset(
        ref=ref("#/pictures/0", tenant="other"), media_type="image/png"
    )
    cross = [bindings[0], AssetBinding(evidence=ref("a", tenant="other"), asset=other)]
    selected = select_evidence_assets(
        cross,
        retained_evidence=[LocatedEvidence(ref=b.evidence) for b in cross],
        allowed_asset_refs=[asset.ref, other.ref],
    )
    assert len(selected.assets) == 2
    with pytest.raises(ValueError, match="source revision"):
        AssetBinding(evidence=ref("a", revision="r2"), asset=asset)


def test_compaction_only_requests_assets_for_retained_citations():
    a = record()
    asset = EvidenceAsset(ref=ref("image"), media_type="image/png")
    a = replace(a, assets=(AssetBinding(evidence=a.evidence.ref, asset=asset),))
    args = dict(
        observations=[observation("old", "a", KnowledgeObservationStage.CITED)],
        evidence=[a],
        activity_order=["old", "current"],
        current_activity_id="current",
        allowed_evidence_refs=[a.evidence.ref],
        allowed_asset_refs=[asset.ref],
    )
    assert len(plan_evidence_compaction(**args).assets.assets) == 1
    assert plan_evidence_compaction(**args, token_budget=0).assets.assets == ()


def test_compaction_rejects_aliases_of_one_canonical_unit():
    a = record()
    with pytest.raises(ValueError, match="one canonical"):
        plan([], [a, replace(a, artifact_id="alias")])


def test_end_to_end_example(capsys):
    from examples.evidence_context_demo import main

    main()
    assert (
        "Declaration: declared; retained evidence units: 1; assets: 1"
        in capsys.readouterr().out
    )
