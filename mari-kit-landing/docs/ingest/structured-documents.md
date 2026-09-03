[]{#structured-documents}[Current]{.current-label}

# Structured and multimodal documents

## At a glance

| Corpus or system | Scale / observation | Design consequence |
|---|---:|---|
| DocLayNet | 80,863 manually annotated pages in 11 layout classes | Page geometry and region kinds need stable representation |
| MMDocRAG | 4,055 expert questions with multimodal evidence chains | Evidence may cross text, tables, and images |
| UniDoc-Bench | More than 70,000 PDF pages and 1,600 questions | Text-image fusion should coexist with exact structure |

## How it works

A `StructuredDocument` preserves a hierarchy of pages and regions. Each `DocumentRegion` has a stable ID, kind, location, optional text, and optional table structure. Generated descriptions and embeddings are `RegionRepresentation` values linked back to the canonical region; they never replace it.

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

Evidence can address a page region or exact table cell. Retrieval may index several representations and fuse their rankings, while answer validation resolves the citation against the original region.

## Parser contract

```{code-block} python
:caption: Adapt any parser without making it a core dependency

class StructuredDocumentParser(Protocol):
    async def parse(self, source: BinaryDocument) -> StructuredDocument: ...

parsed = await docling_adapter.parse(pdf)
for region in parsed.regions:
    exact_index.add(region.region_id, region.searchable_text)
    if region.image_ref:
        image_index.add(region.region_id, embed_image(region.image_ref))
```

Mari supplies the neutral document IR and validation. OCR, VLM inference, file decoding, and model downloads remain adapter responsibilities.

For formats without pages or geometry, use `ParsedDocument` and `ParsedBlock`.
Blocks retain stable IDs, parent relationships, optional source spans, and
format-specific metadata without pretending that chat messages, HTML nodes, or
database rows have PDF coordinates.

```{code-block} python
:caption: Represent a parsed chat thread without a document-layout fiction

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

## What to evaluate

| Layer | Measures |
|---|---|
| Layout | Region mAP, reading-order accuracy, hierarchy accuracy |
| Tables | Cell precision/recall, row/column topology, merged-cell accuracy |
| Retrieval | Evidence recall by modality and cross-modal chain recall |
| Citation | Page, region, and cell localization accuracy |

::: source-block
**Papers and implementations**

[DocLayNet](https://arxiv.org/abs/2206.01062){.paper}[MMDocRAG](https://arxiv.org/abs/2505.16470){.paper}[UniDoc-Bench](https://arxiv.org/abs/2510.03663){.paper}[Docling](https://github.com/docling-project/docling){.paper}

[Docling is MIT licensed. Mari's region types are deliberately smaller and do not copy its parser pipeline.]{.small}
:::
