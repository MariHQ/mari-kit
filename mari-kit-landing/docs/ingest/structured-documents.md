[]{#structured-documents}[Supported]{.current-label}

# Structured and multimodal documents

## Behavior

| Corpus or system | Scale / observation | Design consequence |
|---|---:|---|
| DocLayNet | 80,863 manually annotated pages in 11 layout classes | Page geometry and region kinds need stable representation |
| MMDocRAG | 4,055 expert questions with multimodal evidence chains | Evidence chains span text, tables, and images |
| UniDoc-Bench | More than 70,000 PDF pages and 1,600 questions | Measure text-image fusion beside exact structure |

| Local parser fixture | Before these functions | Current result |
|---|---:|---:|
| Markdown table cells retained | `0/9` | `9/9` |
| HTML recognized blocks with raw spans | `0/7` | `7/7` |
| HTML table cells retained | `6/6` through local adapter | `6/6` through `parse_html` |
| Invalid structural relations reported | `0/5` | `5/5` |

## How it works

A `StructuredDocument` preserves a hierarchy of pages and regions. Each `DocumentRegion` has a stable ID, kind, location, optional text, and optional table structure. Generated descriptions and embeddings are `RegionRepresentation` values linked back to the canonical region. The canonical region remains authoritative.

```{code-block} python
:caption: Preserve a table as structure, text, and page evidence

from mari_components.documents import (
    BoundingBox,
    DocumentRegion,
    RegionKind,
    TableCell,
)

region = DocumentRegion(
    region_id="page-41-table-2",
    page=41,
    kind=RegionKind.TABLE,
    bbox=BoundingBox(left=72, top=188, right=532, bottom=403),
    text="Region | Revenue | Growth",
    cells=(
        TableCell(row=0, column=0, text="Region", header=True),
        TableCell(row=1, column=0, text="Americas"),
        TableCell(row=1, column=1, text="$4.2B"),
    ),
)
```

Evidence can address a page region or exact table cell. Retrieval supports
several representations and can fuse their rankings. Answer validation resolves the
citation against the original region.

## Parser contract

```{code-block} python
:caption: Adapt any parser through a caller-owned dependency

from typing import Protocol
from mari_components.documents import StructuredDocument

# BinaryDocument and docling_adapter are application-defined integration types.
class StructuredDocumentParser(Protocol):
    async def parse(self, source: BinaryDocument) -> StructuredDocument: ...

parsed = await docling_adapter.parse(pdf)
for region in parsed.regions:
    exact_index.add(region.region_id, region.searchable_text)
    if region.image_ref:
        image_index.add(region.region_id, embed_image(region.image_ref))
```

Mari supplies the neutral document IR and its validation functions. Adapters
handle file decoding and OCR. They can also call a VLM or manage model
downloads.

## Definitions and validation options

| Function or value | Inputs | Output / option semantics |
|---|---|---|
| `normalize_table(cells, ...)` | `TableCell` coordinates and row/column spans | `maximum_cells` bounds allocation. `overlap` is `first`, `last`, or `error` |
| `validate_structured_document(document)` | Regions, hierarchy and table cells | Missing parents, parent cycles, and cell-topology violations. Acceptance policy stays with the caller |
| `validate_region_evidence(evidence, document)` | Exact document/revision/region/page and optional cell | Mismatch reasons, resolved text, and all candidate cells. Overlapping coordinates report `ambiguous_cell` and withhold text |
| `DocumentRegion.searchable_text` | Region text or cells | Uses explicit region text first, otherwise joins non-empty cells |

```{code-block} python
:caption: Validate structure before indexing

from mari_components.documents import (
    normalize_table, validate_region_evidence, validate_structured_document,
)

structure = validate_structured_document(document)
if structure.conforms:
    matrix = normalize_table(table_region.cells)

location = validate_region_evidence(citation, document)
if not location.valid:
    review(location.issues)
else:
    index(location.text)
```

Formats that lack page geometry use `ParsedDocument` and `ParsedBlock`.
Blocks retain stable IDs and parent relationships. Optional source spans keep
exact locations when the format supplies them. Format-specific metadata can
describe chat messages, HTML nodes, or database rows in their native terms.

```{code-block} python
:caption: Represent a parsed chat thread with its native conversation structure

from mari_components.documents import ParsedBlock, ParsedDocument

thread = ParsedDocument(
    artifact_id="support-thread:42",
    revision="event-18",
    media_type="application/x-chat",
    blocks=(
        ParsedBlock(block_id="question", kind="message", text="Can I return it?"),
        ParsedBlock(block_id="reply", parent_id="question",
                    kind="message", text="Within 14 days."),
    ),
)
```

## Measures

| Layer | Measures |
|---|---|
| Layout | Region mAP, reading-order accuracy, hierarchy accuracy |
| Tables | Cell precision/recall, row/column topology, merged-cell accuracy |
| Retrieval | Evidence recall by modality and cross-modal chain recall |
| Citation | Page, region, and cell localization accuracy |

::: source-block
**Papers and implementations**

[DocLayNet](https://arxiv.org/abs/2206.01062){.paper}[MMDocRAG](https://arxiv.org/abs/2505.16470){.paper}[UniDoc-Bench](https://arxiv.org/abs/2510.03663){.paper}[Docling](https://github.com/docling-project/docling){.paper}

[Docling is MIT licensed. Mari's region types are deliberately smaller. Its parser pipeline remains separate.]{.small}
:::
