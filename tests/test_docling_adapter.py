from copy import deepcopy

import pytest

from mari_components.documents.docling import adapt_docling_json
from mari_components.references import ObjectRef
from mari_components.retrieval import context_items_from_document


def fixture():
    return {
        "schema_name": "DoclingDocument",
        "version": "1.10.0",
        "body": {
            "self_ref": "#/body",
            "children": [
                {"$ref": "#/texts/0"},
                {"$ref": "#/groups/0"},
                {"$ref": "#/tables/0"},
            ],
        },
        "groups": [{"self_ref": "#/groups/0", "children": [{"$ref": "#/pictures/0"}]}],
        "texts": [
            {
                "self_ref": "#/texts/0",
                "label": "section_header",
                "level": 2,
                "text": "Results",
                "prov": [
                    {
                        "page_no": 1,
                        "bbox": {
                            "l": 1,
                            "t": 90,
                            "r": 20,
                            "b": 80,
                            "coord_origin": "BOTTOMLEFT",
                        },
                    }
                ],
            },
            {"self_ref": "#/texts/1", "label": "caption", "text": "Source caption"},
        ],
        "pictures": [
            {
                "self_ref": "#/pictures/0",
                "label": "picture",
                "captions": [{"$ref": "#/texts/1"}],
                "children": [{"$ref": "#/texts/1"}],
                "image": {"mimetype": "image/jpeg", "uri": "file:///must-not-read.jpg"},
                "meta": {
                    "description": {
                        "text": "Generated interpretation",
                        "model": "vision",
                    }
                },
                "prov": [
                    {
                        "page_no": 1,
                        "bbox": {
                            "l": 1,
                            "t": 20,
                            "r": 40,
                            "b": 50,
                            "coord_origin": "TOPLEFT",
                        },
                    }
                ],
            }
        ],
        "tables": [
            {
                "self_ref": "#/tables/0",
                "label": "table",
                "data": {
                    "table_cells": [
                        {
                            "start_row_offset_idx": 0,
                            "start_col_offset_idx": 0,
                            "row_span": 1,
                            "col_span": 2,
                            "text": "Value",
                            "column_header": True,
                        }
                    ]
                },
                "prov": [{"page_no": 2}],
            }
        ],
        "pages": {"1": {"size": {"width": 100, "height": 100}}},
    }


def adapt(payload):
    return adapt_docling_json(
        payload, source=ObjectRef(namespace="docs", object_id="paper"), revision="r1"
    )


def test_docling_preserves_reading_order_cells_regions_and_separates_generated_text():
    payload = fixture()
    before = deepcopy(payload)
    result = adapt(payload)
    assert result.succeeded
    value = result.values[0]
    assert [b.block_id for b in value.document.blocks] == [
        "#/texts/0",
        "#/pictures/0",
        "#/texts/1",
        "#/tables/0",
    ]
    picture = value.document.blocks[1]
    assert picture.text == "Source caption"
    assert value.document.blocks[2].parent_id == picture.block_id
    assert value.document.blocks[3].cells[0].column_span == 2
    assert value.structured.regions[0].bbox.top == 10
    assert value.structured.regions[0].bbox.bottom == 20
    assert value.structured.representations[0].kind == "generated_description"
    assert value.assets[0].asset.description == "Generated interpretation"
    assert value.assets[0].asset.media_type == "image/jpeg"
    assert all("Generated" not in e.quote for e in value.evidence)
    assert value.evidence[1].quote == ""  # caption is independently addressable
    assert len(result.issues) == 1 and result.issues[0].code == "docling_geometry"
    assert payload == before
    items = context_items_from_document(
        value.document, source=ObjectRef(namespace="docs", object_id="paper")
    )
    assert items[1].section_id == "#/texts/0"
    assert items[1].page_numbers == (1,)
    assert items[1].headings == ("Results",)


def test_docling_rejects_bad_references_cycles_and_unsupported_schemas():
    payload = fixture()
    payload["body"]["children"].append({"$ref": "#/body"})
    with pytest.raises(ValueError, match="cycle"):
        adapt(payload)
    payload = fixture()
    payload["body"]["children"].append({"$ref": "#/texts/900"})
    with pytest.raises(ValueError, match="unresolved"):
        adapt(payload)
    payload = fixture()
    payload["version"] = "2.0.0"
    with pytest.raises(ValueError, match="version"):
        adapt(payload)


def test_legacy_picture_description_and_missing_geometry_do_not_lose_assets():
    payload = fixture()
    picture = payload["pictures"][0]
    picture.pop("meta")
    picture["annotations"] = [
        {
            "kind": "description",
            "text": "legacy generated",
            "provenance": "legacy model",
        }
    ]
    picture["prov"][0]["bbox"]["r"] = float("nan")
    result = adapt(payload)
    assert len(result.issues) == 2
    assert result.values[0].assets[0].asset.description == "legacy generated"
    assert result.values[0].assets[0].asset.description_model == "legacy model"


def test_furniture_in_body_is_excluded_when_requested():
    payload = fixture()
    payload["texts"][0]["content_layer"] = "furniture"
    result = adapt_docling_json(
        payload,
        source=ObjectRef(namespace="docs", object_id="paper"),
        revision="r1",
        include_furniture=False,
    )
    assert "#/texts/0" not in {b.block_id for b in result.values[0].document.blocks}
