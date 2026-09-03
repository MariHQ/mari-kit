"""Stable semantic atoms, temporal versions, and incremental refresh plans."""

from __future__ import annotations

import datetime as dt
import hashlib
import math
import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from . import ParsedBlock, ParsedDocument
from .sequence_diff import DiffKind, DiffSpan, myers_diff, patience_diff

_LIST_ITEM = re.compile(r"^\s*(?:[-+*]|\d+[.)])\s+")
_SPACE = re.compile(r"\s+")
_WORD = re.compile(r"[\w]+", re.UNICODE)


class AtomKind(StrEnum):
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE_ROW = "table_row"
    CODE = "code"
    TEXT_SEGMENT = "text_segment"


@dataclass(frozen=True, slots=True, kw_only=True)
class SemanticAtom:
    atom_id: str
    source_id: str
    source_revision: str
    section_id: str
    heading_path: tuple[str, ...]
    ordinal: int
    kind: AtomKind
    text: str
    content_hash: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if (
            not all(
                value.strip()
                for value in (
                    self.atom_id,
                    self.source_id,
                    self.source_revision,
                    self.text,
                    self.content_hash,
                )
            )
            or self.ordinal < 0
            or self.start < 0
            or self.end <= self.start
        ):
            raise ValueError("semantic atom identity, text, and span are required")
        object.__setattr__(self, "heading_path", tuple(self.heading_path))

    @property
    def contextual_text(self) -> str:
        heading = " > ".join(self.heading_path)
        return f"{heading}\n\n{self.text}" if heading else self.text


@dataclass(frozen=True, slots=True, kw_only=True)
class TemporalAtom:
    atom: SemanticAtom
    valid_from: dt.datetime
    recorded_at: dt.datetime
    valid_to: dt.datetime | None = None
    retracted_at: dt.datetime | None = None
    embedding_model: str = ""
    embedding_version: str = ""

    def __post_init__(self) -> None:
        for name in ("valid_from", "recorded_at"):
            value = getattr(self, name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.valid_to is not None:
            if self.valid_to.tzinfo is None or self.valid_to.utcoffset() is None:
                raise ValueError("valid_to must be timezone-aware")
            if self.valid_to <= self.valid_from:
                raise ValueError("valid_to must be after valid_from")
        if self.retracted_at is not None:
            if (
                self.retracted_at.tzinfo is None
                or self.retracted_at.utcoffset() is None
            ):
                raise ValueError("retracted_at must be timezone-aware")
            if self.retracted_at <= self.recorded_at:
                raise ValueError("retracted_at must be after recorded_at")


class AtomDiffAlgorithm(StrEnum):
    MYERS = "myers"
    PATIENCE = "patience"


@dataclass(frozen=True, slots=True, kw_only=True)
class AtomModification:
    before: SemanticAtom
    after: SemanticAtom
    lexical_similarity: float


@dataclass(frozen=True, slots=True, kw_only=True)
class AtomAlignment:
    algorithm: AtomDiffAlgorithm
    spans: tuple[DiffSpan, ...]
    unchanged: tuple[tuple[SemanticAtom, SemanticAtom], ...]
    modified: tuple[AtomModification, ...]
    inserted: tuple[SemanticAtom, ...]
    deleted: tuple[SemanticAtom, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class AtomRefreshPlan:
    reuse_raw_embeddings: tuple[tuple[str, str], ...]
    reuse_contextual_embeddings: tuple[tuple[str, str], ...]
    embed_raw_atom_ids: tuple[str, ...]
    embed_contextual_atom_ids: tuple[str, ...]
    tombstone_atom_ids: tuple[str, ...]
    invalidate_section_ids: tuple[str, ...]
    invalidate_page_embedding: bool
    rebuild_parent_embeddings_eagerly: bool

    @property
    def reuse_embeddings(self) -> tuple[tuple[str, str], ...]:
        return self.reuse_raw_embeddings

    @property
    def embed_atom_ids(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys((*self.embed_raw_atom_ids, *self.embed_contextual_atom_ids))
        )


def normalize_atom_text(text: str) -> str:
    """Normalize cosmetic whitespace and Unicode without changing word content."""

    return _SPACE.sub(" ", unicodedata.normalize("NFKC", text)).strip()


def semantic_atoms(
    document: ParsedDocument,
    *,
    maximum_atom_characters: int = 2_000,
    fallback_average_characters: int = 1_000,
) -> tuple[SemanticAtom, ...]:
    """Create paragraph, list-item, table-row, and code atoms from parsed blocks."""

    if (
        maximum_atom_characters < 64
        or not 32 <= fallback_average_characters <= maximum_atom_characters
    ):
        raise ValueError("semantic atom size bounds are invalid")
    heading_paths: dict[str, tuple[str, ...]] = {}
    for block in document.blocks:
        if block.kind != "heading":
            continue
        parent_path = heading_paths.get(block.parent_id, ())
        title = str(block.metadata.get("title") or block.text).strip(" #\r\n")
        heading_paths[block.block_id] = (*parent_path, title)
    candidates: list[tuple[AtomKind, str, str, tuple[str, ...], int, int]] = []
    for block in document.blocks:
        if block.kind == "heading" or block.start is None or block.end is None:
            continue
        section_id = block.parent_id or "@root"
        heading_path = heading_paths.get(block.parent_id, ())
        if block.kind == "table":
            candidates.extend(_table_atoms(block, section_id, heading_path))
            continue
        if block.kind == "paragraph":
            lines = block.text.splitlines(keepends=True)
            if any(_LIST_ITEM.match(line) for line in lines):
                cursor = block.start
                prose_start: int | None = None
                prose: list[str] = []
                for line in lines:
                    if _LIST_ITEM.match(line):
                        _append_prose(
                            candidates,
                            prose,
                            prose_start,
                            section_id,
                            heading_path,
                        )
                        prose = []
                        prose_start = None
                        candidates.append(
                            (
                                AtomKind.LIST_ITEM,
                                line,
                                section_id,
                                heading_path,
                                cursor,
                                cursor + len(line),
                            )
                        )
                    elif line.strip():
                        if prose_start is None:
                            prose_start = cursor
                        prose.append(line)
                    else:
                        _append_prose(
                            candidates,
                            prose,
                            prose_start,
                            section_id,
                            heading_path,
                        )
                        prose = []
                        prose_start = None
                    cursor += len(line)
                _append_prose(candidates, prose, prose_start, section_id, heading_path)
                continue
        kind = AtomKind.CODE if block.kind == "code" else AtomKind.PARAGRAPH
        if len(block.text) <= maximum_atom_characters:
            candidates.append(
                (kind, block.text, section_id, heading_path, block.start, block.end)
            )
        else:
            for start, end in content_defined_spans(
                block.text,
                average_characters=fallback_average_characters,
                maximum_characters=maximum_atom_characters,
            ):
                candidates.append(
                    (
                        AtomKind.TEXT_SEGMENT,
                        block.text[start:end],
                        section_id,
                        heading_path,
                        block.start + start,
                        block.start + end,
                    )
                )
    output: list[SemanticAtom] = []
    occurrences: dict[tuple[str, AtomKind, str], int] = {}
    for ordinal, (kind, raw, section_id, heading_path, start, end) in enumerate(
        candidates
    ):
        leading = len(raw) - len(raw.lstrip())
        trailing = len(raw.rstrip())
        text = raw[leading:trailing]
        start += leading
        end = start + len(text)
        if kind is AtomKind.LIST_ITEM:
            marker = _LIST_ITEM.match(text)
            if marker:
                start += marker.end()
                text = text[marker.end() :].strip()
                end = start + len(text)
        normalized = normalize_atom_text(text)
        if not normalized:
            continue
        content_hash = hashlib.sha256(normalized.encode()).hexdigest()
        occurrence_key = (section_id, kind, content_hash)
        occurrences[occurrence_key] = occurrences.get(occurrence_key, 0) + 1
        identity = "\0".join(
            (
                document.artifact_id,
                section_id,
                kind.value,
                content_hash,
                str(occurrences[occurrence_key]),
            )
        )
        output.append(
            SemanticAtom(
                atom_id=f"atom:{hashlib.sha256(identity.encode()).hexdigest()[:24]}",
                source_id=document.artifact_id,
                source_revision=document.revision,
                section_id=section_id,
                heading_path=heading_path,
                ordinal=ordinal,
                kind=kind,
                text=text,
                content_hash=content_hash,
                start=start,
                end=end,
            )
        )
    return tuple(output)


def content_defined_spans(
    text: str,
    *,
    minimum_characters: int | None = None,
    average_characters: int = 1_000,
    maximum_characters: int = 2_000,
) -> tuple[tuple[int, int], ...]:
    """Return stable FastCDC-inspired fallback spans for oversized text blocks."""

    minimum = minimum_characters or max(32, average_characters // 2)
    if not 1 <= minimum <= average_characters <= maximum_characters:
        raise ValueError("content-defined span bounds are invalid")
    if not text:
        return ()
    bits = max(1, round(math.log2(average_characters)))
    mask = (1 << bits) - 1
    gear = tuple(
        int.from_bytes(hashlib.sha256(bytes([value])).digest()[:8], "big")
        for value in range(256)
    )
    spans: list[tuple[int, int]] = []
    start = 0
    fingerprint = 0
    for index, character in enumerate(text):
        fingerprint = ((fingerprint << 1) + gear[ord(character) & 255]) & (
            (1 << 64) - 1
        )
        size = index + 1 - start
        natural = size >= minimum and not (fingerprint & mask) and character.isspace()
        if natural or size >= maximum_characters:
            spans.append((start, index + 1))
            start = index + 1
            fingerprint = 0
    if start < len(text):
        spans.append((start, len(text)))
    return tuple(spans)


def align_atoms(
    old: Sequence[SemanticAtom],
    new: Sequence[SemanticAtom],
    *,
    algorithm: AtomDiffAlgorithm = AtomDiffAlgorithm.PATIENCE,
    modification_threshold: float = 0.55,
) -> AtomAlignment:
    """Align hashes exactly, then pair similar replacements for provenance."""

    if not 0 <= modification_threshold <= 1:
        raise ValueError("modification threshold must be in [0, 1]")
    hashes_old = tuple(atom.content_hash for atom in old)
    hashes_new = tuple(atom.content_hash for atom in new)
    spans = (
        patience_diff(hashes_old, hashes_new)
        if algorithm is AtomDiffAlgorithm.PATIENCE
        else myers_diff(hashes_old, hashes_new)
    )
    unchanged: list[tuple[SemanticAtom, SemanticAtom]] = []
    modified: list[AtomModification] = []
    inserted: list[SemanticAtom] = []
    deleted: list[SemanticAtom] = []
    for span in spans:
        if span.kind is DiffKind.EQUAL:
            unchanged.extend(
                zip(
                    old[span.old_start : span.old_end],
                    new[span.new_start : span.new_end],
                    strict=True,
                )
            )
            continue
        before = list(old[span.old_start : span.old_end])
        after = list(new[span.new_start : span.new_end])
        matches: list[tuple[float, int, int]] = []
        for left, old_atom in enumerate(before):
            for right, new_atom in enumerate(after):
                if (
                    old_atom.kind is new_atom.kind
                    and old_atom.heading_path == new_atom.heading_path
                ):
                    similarity = _lexical_similarity(old_atom.text, new_atom.text)
                    if similarity >= modification_threshold:
                        matches.append((similarity, left, right))
        used_old: set[int] = set()
        used_new: set[int] = set()
        for similarity, left, right in sorted(
            matches, key=lambda item: (-item[0], item[1], item[2])
        ):
            if left in used_old or right in used_new:
                continue
            used_old.add(left)
            used_new.add(right)
            modified.append(
                AtomModification(
                    before=before[left],
                    after=after[right],
                    lexical_similarity=similarity,
                )
            )
        deleted.extend(
            atom for index, atom in enumerate(before) if index not in used_old
        )
        inserted.extend(
            atom for index, atom in enumerate(after) if index not in used_new
        )
    return AtomAlignment(
        algorithm=algorithm,
        spans=spans,
        unchanged=tuple(unchanged),
        modified=tuple(modified),
        inserted=tuple(inserted),
        deleted=tuple(deleted),
    )


def plan_atom_refresh(
    alignment: AtomAlignment, *, rebuild_parent_embeddings_eagerly: bool = False
) -> AtomRefreshPlan:
    """Plan atom embedding reuse and parent invalidation without executing writes."""

    changed_new = (*alignment.inserted, *(item.after for item in alignment.modified))
    changed_old = (*alignment.deleted, *(item.before for item in alignment.modified))
    moved = tuple(
        (before, after)
        for before, after in alignment.unchanged
        if before.contextual_text != after.contextual_text
        or before.section_id != after.section_id
    )
    contextual_reuse = tuple(
        (before.atom_id, after.atom_id)
        for before, after in alignment.unchanged
        if (before, after) not in moved
    )
    sections = {
        atom.section_id
        for atom in (
            *changed_new,
            *changed_old,
            *(before for before, _ in moved),
            *(after for _, after in moved),
        )
    }
    return AtomRefreshPlan(
        reuse_raw_embeddings=tuple(
            (before.atom_id, after.atom_id) for before, after in alignment.unchanged
        ),
        reuse_contextual_embeddings=contextual_reuse,
        embed_raw_atom_ids=tuple(atom.atom_id for atom in changed_new),
        embed_contextual_atom_ids=tuple(
            dict.fromkeys(
                (
                    *(atom.atom_id for atom in changed_new),
                    *(after.atom_id for _, after in moved),
                )
            )
        ),
        tombstone_atom_ids=tuple(
            dict.fromkeys(
                (
                    *(atom.atom_id for atom in changed_old),
                    *(
                        before.atom_id
                        for before, after in moved
                        if before.atom_id != after.atom_id
                    ),
                )
            )
        ),
        invalidate_section_ids=tuple(sorted(sections)),
        invalidate_page_embedding=bool(changed_new or changed_old or moved),
        rebuild_parent_embeddings_eagerly=rebuild_parent_embeddings_eagerly,
    )


def active_atoms(
    versions: Iterable[TemporalAtom], *, at: dt.datetime, known_at: dt.datetime
) -> tuple[TemporalAtom, ...]:
    """Select atom versions valid at one time and recorded by another."""

    if (
        at.tzinfo is None
        or at.utcoffset() is None
        or known_at.tzinfo is None
        or known_at.utcoffset() is None
    ):
        raise ValueError("atom query times must be timezone-aware")
    return tuple(
        sorted(
            (
                item
                for item in versions
                if item.valid_from <= at
                and (item.valid_to is None or at < item.valid_to)
                and item.recorded_at <= known_at
                and (item.retracted_at is None or known_at < item.retracted_at)
            ),
            key=lambda item: (
                item.atom.source_id,
                item.atom.ordinal,
                item.atom.atom_id,
            ),
        )
    )


def _table_atoms(
    block: ParsedBlock, section_id: str, heading_path: tuple[str, ...]
) -> list[tuple[AtomKind, str, str, tuple[str, ...], int, int]]:
    if block.start is None:
        return []
    lines = block.text.splitlines(keepends=True)
    output: list[tuple[AtomKind, str, str, tuple[str, ...], int, int]] = []
    cursor = block.start
    for index, line in enumerate(lines):
        divider = index == 1 and re.match(r"^\s*\|?\s*:?-", line)
        if not divider and line.strip():
            output.append(
                (
                    AtomKind.TABLE_ROW,
                    line,
                    section_id,
                    heading_path,
                    cursor,
                    cursor + len(line),
                )
            )
        cursor += len(line)
    return output


def _append_prose(
    candidates: list[tuple[AtomKind, str, str, tuple[str, ...], int, int]],
    lines: Sequence[str],
    start: int | None,
    section_id: str,
    heading_path: tuple[str, ...],
) -> None:
    if lines and start is not None:
        raw = "".join(lines)
        candidates.append(
            (
                AtomKind.PARAGRAPH,
                raw,
                section_id,
                heading_path,
                start,
                start + len(raw),
            )
        )


def _lexical_similarity(left: str, right: str) -> float:
    a = set(_WORD.findall(normalize_atom_text(left).casefold()))
    b = set(_WORD.findall(normalize_atom_text(right).casefold()))
    return len(a & b) / len(a | b) if a or b else 1.0
