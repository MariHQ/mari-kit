"""Adapt Docling's exported document tree without importing its runtime.

Based on haiku.rag's structural extraction; see THIRD_PARTY_NOTICES.md.
Pass ``document.model_dump(mode='json')`` from a live DoclingDocument. Conversion,
OCR, image decoding, filesystem access, and provider calls remain external.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from mari_components.knowledge.multimodal import AssetBinding, EvidenceAsset
from mari_components.references import (
    JsonPointer,
    LocatedEvidence,
    ObjectRef,
    RevisionRef,
)

from . import (
    BoundingBox,
    DocumentRegion,
    ParsedBlock,
    ParsedDocument,
    RegionKind,
    RegionRepresentation,
    StructuredDocument,
    TableCell,
)
from .results import ParseIssue, ParseIssueSeverity, ParseResult


@dataclass(frozen=True, slots=True, kw_only=True)
class DoclingAdaptation:
    document: ParsedDocument
    structured: StructuredDocument
    evidence: tuple[LocatedEvidence, ...]
    assets: tuple[AssetBinding, ...]


def adapt_docling_json(
    payload: Mapping[str, Any],
    *,
    source: ObjectRef,
    revision: str,
    media_type: str = "application/pdf",
    include_furniture: bool = True,
) -> ParseResult[DoclingAdaptation]:
    """Preserve reading order, table cells, pages, hierarchy, and source pointers.

    Generated picture descriptions remain separate representations and never
    become quoted source text. Coordinates are normalized to top-left page units.
    Invalid/missing geometry is reported without inventing a page region. Image
    URIs and embedded bytes are deliberately left in the caller's source object.
    """
    if payload.get("schema_name") != "DoclingDocument":
        raise ValueError("expected a DoclingDocument JSON export")
    if str(payload.get("version", "")).split(".")[0] != "1":
        raise ValueError("unsupported DoclingDocument schema major version")
    # Validate source revision even for an empty document.
    RevisionRef(object=source, revision=revision)
    blocks: list[ParsedBlock] = []
    regions: list[DocumentRegion] = []
    representations: list[RegionRepresentation] = []
    evidence: list[LocatedEvidence] = []
    assets: list[AssetBinding] = []
    issues: list[ParseIssue] = []
    visited: set[str] = set()
    roots = ["#/body"] + (
        ["#/furniture"] if include_furniture and "furniture" in payload else []
    )
    stack = [(ref, "", 0) for ref in reversed(roots)]
    while stack:
        pointer, parent, depth = stack.pop()
        if pointer in visited:
            raise ValueError(
                "Docling reading-order tree contains a cycle or repeated child"
            )
        visited.add(pointer)
        item = _resolve(payload, pointer)
        if item.get("self_ref") != pointer:
            raise ValueError("Docling self_ref does not match its tree reference")
        if not include_furniture and item.get("content_layer") == "furniture":
            continue
        label = str(item.get("label", "group"))
        is_container = pointer in roots or pointer.startswith("#/groups/")
        block_parent = parent
        if not is_container:
            ref = RevisionRef(object=source, revision=revision, unit_id=pointer)
            captions = tuple(
                str(_resolve(payload, _ref(value)).get("text", ""))
                for value in item.get("captions", ())
            )
            cells = _cells(item) if label == "table" else ()
            text = str(item.get("text", ""))
            if label == "picture":
                text = "\n".join(captions)
            elif label == "table" and not text:
                rows: dict[int, list[TableCell]] = {}
                for cell in cells:
                    rows.setdefault(cell.row, []).append(cell)
                text = "\n".join(
                    "\t".join(
                        cell.text for cell in sorted(row, key=lambda cell: cell.column)
                    )
                    for _, row in sorted(rows.items())
                )
            prov = item.get("prov", ())
            pages = sorted({int(value["page_no"]) for value in prov})
            if any(page < 1 for page in pages):
                raise ValueError("Docling page numbers must be positive")
            blocks.append(
                ParsedBlock(
                    block_id=pointer,
                    kind=label,
                    text=text,
                    parent_id=parent,
                    cells=cells,
                    metadata={
                        "source_pointer": pointer,
                        "page_numbers": pages,
                        "heading_level": int(item.get("level", 1)),
                        "tree_depth": depth,
                        "caption_refs": [
                            _ref(value) for value in item.get("captions", ())
                        ],
                    },
                )
            )
            # Rendered tables and joined captions are not verbatim source quotes.
            evidence.append(
                LocatedEvidence(
                    ref=ref,
                    locator=JsonPointer(pointer=pointer[1:]),
                    quote=str(item.get("text", ""))
                    if label not in {"picture", "table"}
                    else "",
                )
            )
            description, model = _description(item)
            if label == "picture":
                image = item.get("image") or {}
                asset = EvidenceAsset(
                    ref=ref,
                    media_type=str(image.get("mimetype") or "application/octet-stream"),
                    captions=captions,
                    description=description,
                    description_model=model,
                )
                assets.append(AssetBinding(evidence=ref, asset=asset))
            for index, value in enumerate(prov):
                region_id = f"{pointer}/prov/{index}"
                try:
                    bbox = _bbox(value, payload.get("pages", {}))
                    region = DocumentRegion(
                        region_id=region_id,
                        page=int(value["page_no"]),
                        kind=_region_kind(label),
                        bbox=bbox,
                        text=text,
                        cells=cells,
                        image_ref=pointer if label == "picture" else "",
                    )
                except (KeyError, TypeError, ValueError) as error:
                    issues.append(
                        ParseIssue(
                            code="docling_geometry",
                            message=str(error),
                            severity=ParseIssueSeverity.WARNING,
                            subject=region_id,
                        )
                    )
                    continue
                regions.append(region)
                if description:
                    representations.append(
                        RegionRepresentation(
                            region_id=region_id,
                            kind="generated_description",
                            content=description,
                            model=model,
                        )
                    )
            block_parent = pointer
        children = item.get("children", ())
        stack.extend(
            (_ref(child), block_parent, depth + 1) for child in reversed(children)
        )
    adaptation = DoclingAdaptation(
        document=ParsedDocument(
            artifact_id=source.object_id,
            revision=revision,
            media_type=media_type,
            blocks=tuple(blocks),
        ),
        structured=StructuredDocument(
            document_id=source.object_id,
            revision=revision,
            regions=tuple(regions),
            representations=tuple(representations),
        ),
        evidence=tuple(evidence),
        assets=tuple(assets),
    )
    return ParseResult(
        values=(adaptation,),
        issues=tuple(issues),
        parser="docling-json-v1",
        source_revision=revision,
    )


def _ref(value: Mapping[str, Any]) -> str:
    pointer = value.get("$ref")
    if not isinstance(pointer, str):
        raise ValueError("Docling child must contain a string $ref")
    return pointer


def _resolve(payload: Mapping[str, Any], pointer: str) -> Mapping[str, Any]:
    if not pointer.startswith("#/"):
        raise ValueError("Docling references must be local JSON pointers")
    value: Any = payload
    try:
        for part in pointer[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            if isinstance(value, list):
                if not part.isdecimal():
                    raise ValueError("invalid array index")
                value = value[int(part)]
            else:
                value = value[part]
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise ValueError(f"unresolved Docling pointer: {pointer}") from error
    if not isinstance(value, Mapping):
        raise ValueError("Docling pointer must resolve to an object")
    return value


def _cells(item: Mapping[str, Any]) -> tuple[TableCell, ...]:
    return tuple(
        TableCell(
            row=int(cell["start_row_offset_idx"]),
            column=int(cell["start_col_offset_idx"]),
            row_span=int(cell.get("row_span", 1)),
            column_span=int(cell.get("col_span", 1)),
            text=str(cell.get("text", "")),
            header=bool(cell.get("column_header") or cell.get("row_header")),
        )
        for cell in (item.get("data") or {}).get("table_cells", ())
    )


def _description(item: Mapping[str, Any]) -> tuple[str, str]:
    description = (item.get("meta") or {}).get("description") or {}
    if description:
        return str(description.get("text", "")), str(description.get("model", ""))
    # Older exports use annotations; unlike a live DoclingDocument they have not
    # run Docling's migration validator.
    for annotation in item.get("annotations", ()):
        if annotation.get("kind") == "description":
            return str(annotation.get("text", "")), str(
                annotation.get("provenance", "")
            )
    return "", ""


def _bbox(prov: Mapping[str, Any], pages: Mapping[str, Any]) -> BoundingBox:
    box = prov["bbox"]
    left, top, right, bottom = (float(box[key]) for key in ("l", "t", "r", "b"))
    origin = box.get("coord_origin", "TOPLEFT")
    if origin == "BOTTOMLEFT":
        height = float(pages[str(prov["page_no"])]["size"]["height"])
        if not math.isfinite(height) or height <= 0:
            raise ValueError("invalid page height")
        top, bottom = height - top, height - bottom
    elif origin != "TOPLEFT":
        raise ValueError("unknown coordinate origin")
    if not all(math.isfinite(value) for value in (left, top, right, bottom)):
        raise ValueError("nonfinite Docling bounding box")
    return BoundingBox(left=left, top=top, right=right, bottom=bottom)


def _region_kind(label: str) -> RegionKind:
    return {
        "picture": RegionKind.FIGURE,
        "table": RegionKind.TABLE,
        "section_header": RegionKind.HEADING,
        "title": RegionKind.HEADING,
        "page_header": RegionKind.HEADER,
        "page_footer": RegionKind.FOOTER,
        "formula": RegionKind.FORMULA,
        "code": RegionKind.CODE,
    }.get(label, RegionKind.TEXT)
