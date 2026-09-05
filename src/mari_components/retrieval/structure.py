"""Section-aware context windows with exact retained spans and provenance.

Adapted from haiku.rag/context.py; see THIRD_PARTY_NOTICES.md.
Fetching source items, authorization, and tokenization remain caller-owned.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, replace

from mari_components.documents import ParsedDocument
from mari_components.documents.atoms import SemanticAtom
from mari_components.references import (
    JsonPointer,
    LocatedEvidence,
    ObjectRef,
    RevisionRef,
    TextSpan,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class StructuredContextItem:
    evidence: LocatedEvidence
    ordinal: int
    section_id: str = ""
    label: str = "text"
    page_numbers: tuple[int, ...] = ()
    headings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.ordinal < 0 or not self.evidence.ref.unit_id:
            raise ValueError("context items require an ordinal and unit reference")
        if any(page < 1 for page in self.page_numbers):
            raise ValueError("page numbers must be positive")
        object.__setattr__(self, "page_numbers", tuple(sorted(set(self.page_numbers))))
        object.__setattr__(self, "headings", tuple(self.headings))
        locator = self.evidence.locator
        if isinstance(locator, TextSpan) and locator.end - locator.start != len(
            self.evidence.quote
        ):
            raise ValueError("text-span evidence must contain the exact source slice")


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextHit:
    ref: RevisionRef
    score: float = 0.0
    span: TextSpan | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.score):
            raise ValueError("hit score must be finite")


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextExpansionPolicy:
    max_chars: int
    excluded_labels: frozenset[str] = frozenset()
    tight_labels: frozenset[str] = frozenset(
        {"picture", "figure", "table", "table_row"}
    )
    minimum_section_ratio: float = 0.2
    anchor_chars: int = 128
    separator: str = "\n\n"

    def __post_init__(self) -> None:
        if self.max_chars < 1 or self.anchor_chars < 1:
            raise ValueError("context and anchor budgets must be positive")
        if not 0 <= self.minimum_section_ratio <= 1:
            raise ValueError("minimum section ratio must be between zero and one")
        object.__setattr__(self, "excluded_labels", frozenset(self.excluded_labels))
        object.__setattr__(self, "tight_labels", frozenset(self.tight_labels))


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextFragment:
    evidence: LocatedEvidence
    item_span: TextSpan
    page_numbers: tuple[int, ...]
    headings: tuple[str, ...]
    label: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ExpandedContext:
    text: str
    primary_ref: RevisionRef
    matched_refs: tuple[RevisionRef, ...]
    fragments: tuple[ContextFragment, ...]
    score: float

    @property
    def page_numbers(self) -> tuple[int, ...]:
        return tuple(
            sorted(
                {page for fragment in self.fragments for page in fragment.page_numbers}
            )
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextExpansionResult:
    windows: tuple[ExpandedContext, ...]
    unavailable_refs: tuple[RevisionRef, ...]
    over_budget_refs: tuple[RevisionRef, ...]


def context_items_from_atoms(
    atoms: Iterable[SemanticAtom], *, source: ObjectRef
) -> tuple[StructuredContextItem, ...]:
    """Use existing semantic atoms without creating another document identity."""
    return tuple(
        StructuredContextItem(
            evidence=atom.located_evidence(source=source),
            ordinal=atom.ordinal,
            section_id=atom.section_id,
            label=atom.kind.value,
            headings=atom.heading_path,
        )
        for atom in atoms
    )


def context_items_from_document(
    document: ParsedDocument, *, source: ObjectRef
) -> tuple[StructuredContextItem, ...]:
    """Adapt parser blocks, retaining source offsets or structural pointers."""
    if source.object_id != document.artifact_id:
        raise ValueError("document and source object IDs must match")
    output: list[StructuredContextItem] = []
    section = ""
    headings: list[str] = []
    for ordinal, block in enumerate(document.blocks):
        if block.kind in {"heading", "section_header", "title"}:
            section = block.block_id
            level = int(
                block.metadata.get("heading_level", block.metadata.get("level", 1))
            )
            headings = headings[: max(0, level - 1)] + [block.text]
        pointer = str(block.metadata.get("source_pointer", ""))
        locator = (
            TextSpan(start=block.start, end=block.end)
            if block.start is not None
            and block.end is not None
            and block.end - block.start == len(block.text)
            else JsonPointer(pointer=pointer.removeprefix("#"))
            if pointer
            else None
        )
        output.append(
            StructuredContextItem(
                evidence=LocatedEvidence(
                    ref=RevisionRef(
                        object=source,
                        revision=document.revision,
                        unit_id=block.block_id,
                    ),
                    locator=locator,
                    quote=block.text,
                ),
                ordinal=ordinal,
                section_id=section,
                label=block.kind,
                page_numbers=tuple(
                    int(page) for page in block.metadata.get("page_numbers", ())
                ),
                headings=tuple(headings),
            )
        )
    return tuple(output)


def expand_structured_context(
    items: Iterable[StructuredContextItem],
    hits: Iterable[ContextHit],
    *,
    policy: ContextExpansionPolicy,
    allowed_refs: Iterable[RevisionRef],
) -> ContextExpansionResult:
    """Expand independently per source revision, with a budget per output window.

    Explicit hit spans must survive whole; oversized spans are reported. Without
    a span, a central anchor of up to ``anchor_chars`` is retained. Output spans
    describe any clipping exactly. Overlapping windows merge only when every
    anchor fits; adjacency alone never merges windows. No global budget is
    implied: hosts can pack these windows using their tokenizer afterwards.
    """
    values = tuple(items)
    by_ref = {item.evidence.ref: item for item in values}
    if len(by_ref) != len(values):
        raise ValueError("context item references must be unique")
    requested = tuple(hits)
    if len({hit.ref for hit in requested}) != len(requested):
        raise ValueError("hit references must be unique")
    if any(hit.ref not in by_ref for hit in requested):
        raise ValueError("hit references an unknown context item")
    allowed = set(allowed_refs)
    unavailable = tuple(hit.ref for hit in requested if hit.ref not in allowed)
    oversized: list[RevisionRef] = []
    anchors: dict[RevisionRef, TextSpan] = {}
    for hit in requested:
        if hit.ref not in allowed:
            continue
        length = len(by_ref[hit.ref].evidence.quote)
        if hit.span is not None:
            if hit.span.end > length or (length and hit.span.start == hit.span.end):
                raise ValueError("hit span must address nonempty item text")
            anchor = hit.span
        else:
            width = min(length, policy.anchor_chars, policy.max_chars)
            start = (length - width) // 2
            anchor = TextSpan(start=start, end=start + width)
        if anchor.end - anchor.start > policy.max_chars:
            oversized.append(hit.ref)
        else:
            anchors[hit.ref] = anchor
    # Partition at unauthorized items; neighboring text must not bridge them.
    groups: dict[tuple[ObjectRef, str], list[StructuredContextItem]] = {}
    for item in values:
        ref = item.evidence.ref
        groups.setdefault((ref.object, ref.revision), []).append(item)
    windows: list[ExpandedContext] = []
    hit_map = {hit.ref: hit for hit in requested}
    for members in groups.values():
        members.sort(key=lambda item: item.ordinal)
        if len({item.ordinal for item in members}) != len(members):
            raise ValueError("item ordinals must be unique within a source revision")
        segment: list[StructuredContextItem] = []
        for item in (*members, None):
            if item is not None and item.evidence.ref in allowed:
                if (
                    item.label not in policy.excluded_labels
                    or item.evidence.ref in anchors
                ):
                    segment.append(item)
                continue
            if segment:
                windows.extend(_expand_segment(segment, anchors, hit_map, policy))
                segment = []
    windows.sort(key=lambda window: (-window.score, window.primary_ref.key))
    return ContextExpansionResult(
        windows=tuple(windows),
        unavailable_refs=unavailable,
        over_budget_refs=tuple(oversized),
    )


def _expand_segment(
    items: list[StructuredContextItem],
    anchors: dict[RevisionRef, TextSpan],
    hits: dict[RevisionRef, ContextHit],
    policy: ContextExpansionPolicy,
) -> list[ExpandedContext]:
    ranges: list[tuple[int, int, list[RevisionRef]]] = []
    # Rendering uses one separator between items, including empty figure units.
    starts: list[int] = []
    cursor = 0
    for item in items:
        starts.append(cursor)
        cursor += len(item.evidence.quote) + len(policy.separator)

    def size(lo: int, hi: int) -> int:
        return starts[hi] + len(items[hi].evidence.quote) - starts[lo]

    def absolute(ref: RevisionRef) -> tuple[int, int]:
        idx = index[ref]
        anchor = anchors[ref]
        return starts[idx] + anchor.start, starts[idx] + anchor.end

    index = {item.evidence.ref: idx for idx, item in enumerate(items)}
    for idx, item in enumerate(items):
        ref = item.evidence.ref
        if ref not in anchors:
            continue
        lo = hi = idx
        while lo > 0 and items[lo - 1].section_id == item.section_id:
            lo -= 1
        while hi + 1 < len(items) and items[hi + 1].section_id == item.section_id:
            hi += 1
        section_size = size(lo, hi)
        if section_size > policy.max_chars:
            bound_lo, bound_hi = lo, hi
            lo = hi = idx
        elif (
            section_size < policy.max_chars * policy.minimum_section_ratio
            and item.label not in policy.tight_labels
        ):
            bound_lo, bound_hi = 0, len(items) - 1
        else:
            ranges.append((lo, hi, [ref]))
            continue
        while size(lo, hi) < policy.max_chars and (lo > bound_lo or hi < bound_hi):
            if lo > bound_lo:
                lo -= 1
            if size(lo, hi) < policy.max_chars and hi < bound_hi:
                hi += 1
        ranges.append((lo, hi, [ref]))
    ranges.sort(key=lambda row: row[0])
    merged: list[tuple[int, int, list[RevisionRef]]] = []
    for lo, hi, refs in ranges:
        if merged and lo <= merged[-1][1]:
            prior_lo, prior_hi, prior_refs = merged[-1]
            combined = [*prior_refs, *refs]
            extent = [absolute(ref) for ref in combined]
            if (
                max(end for _, end in extent) - min(start for start, _ in extent)
                <= policy.max_chars
            ):
                merged[-1] = prior_lo, max(hi, prior_hi), combined
                continue
        merged.append((lo, hi, refs))
    output: list[ExpandedContext] = []
    for lo, hi, refs in merged:
        primary = min(refs, key=lambda ref: (-hits[ref].score, ref.key))
        minimum = min(absolute(ref)[0] for ref in refs)
        maximum = max(absolute(ref)[1] for ref in refs)
        left = starts[lo]
        right = starts[hi] + len(items[hi].evidence.quote)
        if right - left > policy.max_chars:
            center_start, center_end = absolute(primary)
            start = (center_start + center_end - policy.max_chars) // 2
            left = max(left, min(start, minimum, right - policy.max_chars))
            left = max(left, maximum - policy.max_chars)
            right = min(right, left + policy.max_chars)
        fragments: list[ContextFragment] = []
        for idx in range(lo, hi + 1):
            item = items[idx]
            text = item.evidence.quote
            start, end = max(0, left - starts[idx]), min(len(text), right - starts[idx])
            if end <= start and not (not text and left <= starts[idx] <= right):
                continue
            locator = item.evidence.locator
            if isinstance(locator, TextSpan):
                locator = TextSpan(start=locator.start + start, end=locator.start + end)
            fragments.append(
                ContextFragment(
                    evidence=replace(
                        item.evidence, quote=text[start:end], locator=locator
                    ),
                    item_span=TextSpan(start=start, end=end),
                    page_numbers=item.page_numbers,
                    headings=item.headings,
                    label=item.label,
                )
            )
        joined = policy.separator.join(
            item.evidence.quote for item in items[lo : hi + 1]
        )
        output.append(
            ExpandedContext(
                text=joined[left - starts[lo] : right - starts[lo]],
                primary_ref=primary,
                matched_refs=tuple(refs),
                fragments=tuple(fragments),
                score=hits[primary].score,
            )
        )
    return output
