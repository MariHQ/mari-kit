"""Run with python -m examples.evidence_context_demo; no services required."""

from mari_components.documents.docling import adapt_docling_json
from mari_components.knowledge import (
    CitationEvent,
    CitationEventKind,
    CompactionEvidence,
    KnowledgeObservation,
    KnowledgeObservationStage,
    OwnedEvidenceRef,
    inspect_citation_declarations,
    plan_evidence_compaction,
    select_evidence_assets,
)
from mari_components.references import ObjectRef
from mari_components.retrieval import (
    ContextExpansionPolicy,
    ContextHit,
    context_items_from_document,
    expand_structured_context,
)


def main() -> None:
    source = ObjectRef(namespace="reports", object_id="revenue")
    # A host would obtain this JSON from Docling's model_dump(mode="json").
    exported = {
        "schema_name": "DoclingDocument",
        "version": "1.10.0",
        "body": {
            "self_ref": "#/body",
            "children": [{"$ref": "#/texts/0"}, {"$ref": "#/pictures/0"}],
        },
        "texts": [
            {
                "self_ref": "#/texts/0",
                "label": "section_header",
                "text": "Revenue",
                "level": 1,
            },
            {
                "self_ref": "#/texts/1",
                "label": "caption",
                "text": "Revenue grew 12% in Q2.",
            },
        ],
        "pictures": [
            {
                "self_ref": "#/pictures/0",
                "label": "picture",
                "captions": [{"$ref": "#/texts/1"}],
                "image": {"mimetype": "image/png"},
                "meta": {
                    "description": {
                        "text": "An upward bar chart",
                        "model": "host-vision-model",
                    }
                },
            }
        ],
    }
    adapted = adapt_docling_json(exported, source=source, revision="r1").values[0]
    items = context_items_from_document(adapted.document, source=source)
    figure = items[1].evidence.ref
    # The host computes authorized, current unit and asset references.
    allowed = [item.evidence.ref for item in items]
    asset_refs = [binding.asset.ref for binding in adapted.assets]
    expanded = expand_structured_context(
        items,
        [ContextHit(ref=figure, score=0.9)],
        policy=ContextExpansionPolicy(max_chars=200),
        allowed_refs=allowed,
    )
    retained = [
        fragment.evidence
        for window in expanded.windows
        for fragment in window.fragments
    ]
    assets = select_evidence_assets(
        adapted.assets, retained_evidence=retained, allowed_asset_refs=asset_refs
    )
    assert len(assets.assets) == 1
    assert "An upward bar chart" not in expanded.windows[0].text

    owned = OwnedEvidenceRef(owner="report-search", ref=figure)
    declaration = inspect_citation_declarations(
        [
            CitationEvent(
                event_id="search-1",
                activity_id="q1",
                owner="report-search",
                ordinal=0,
                kind=CitationEventKind.OUTCOME,
                refs=(owned,),
            ),
            CitationEvent(
                event_id="cite-1",
                activity_id="q1",
                owner="answer",
                ordinal=1,
                kind=CitationEventKind.DECLARATION,
                refs=(owned,),
            ),
        ],
        activity_id="q1",
    )
    assert declaration.refs == (owned,)
    observations = [
        KnowledgeObservation(
            observation_id=f"q1-{stage.name}",
            activity_id="q1",
            artifact_id="reports:revenue:figure",
            revision="r1",
            stage=stage,
            ordinal=index,
        )
        for index, stage in enumerate(
            (
                KnowledgeObservationStage.RETRIEVED,
                KnowledgeObservationStage.SHOWN,
                KnowledgeObservationStage.CITED,
            )
        )
    ]
    cited = next(value for value in retained if value.ref == figure)
    compacted = plan_evidence_compaction(
        observations,
        [
            CompactionEvidence(
                artifact_id="reports:revenue:figure",
                evidence=cited,
                token_count=32,
                assets=adapted.assets,
            )
        ],
        activity_order=["q1", "q2"],
        current_activity_id="q2",
        allowed_evidence_refs=allowed,
        allowed_asset_refs=asset_refs,
        token_budget=64,
    )
    assert compacted.groups[0].evidence[0].evidence == cited
    assert len(compacted.assets.assets) == 1
    print(expanded.windows[0].text)
    print(
        f"Declaration: {declaration.status.value}; retained evidence units: {len(compacted.groups[0].evidence)}; assets: {len(compacted.assets.assets)}"
    )
    # The host loads assets and renders this plan into its runtime's messages.


if __name__ == "__main__":
    main()
