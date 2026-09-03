"""Dependency-free structural Markdown parsing with exact character spans."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence

from . import ParsedBlock, ParsedDocument, TableCell
from .results import ParseIssue, ParseIssueSeverity, ParseResult, stable_source_id

_ATX = re.compile(r"^( {0,3})(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*(?:\n|$)")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})([^\n]*)(?:\n|$)")
_TABLE_DIVIDER = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
_SLUG = re.compile(r"[^a-z0-9]+")


def _slug(value: str) -> str:
    return _SLUG.sub("-", value.casefold()).strip("-") or "section"


def _table_values(line: str) -> tuple[str, ...]:
    value = line.rstrip("\r\n").strip()
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|") and not value.endswith(r"\|"):
        value = value[:-1]
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for character in value:
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(character)
    if escaped:
        current.append("\\")
    cells.append("".join(current).strip())
    return tuple(cells)


def parse_markdown(
    text: str,
    *,
    artifact_id: str,
    revision: str,
    parser_id: str = "mari.markdown@1",
    tables: bool = True,
    recover_unclosed_fences: bool = True,
) -> ParseResult[ParsedDocument]:
    """Parse block structure while retaining exact character spans and tables."""

    lines = text.splitlines(keepends=True)
    offsets: list[int] = []
    offset = 0
    for line in lines:
        offsets.append(offset)
        offset += len(line)
    if not lines and text == "":
        lines = []
    blocks: list[ParsedBlock] = []
    issues: list[ParseIssue] = []
    heading_path: list[str] = []
    heading_ids: list[str] = []
    occurrences: dict[tuple[str, str, str], int] = {}

    def add_block(
        kind: str,
        start_line: int,
        end_line: int,
        *,
        parent_id: str = "",
        cells: Sequence[TableCell] = (),
        metadata: dict[str, object] | None = None,
        readable_id: str = "",
    ) -> None:
        start = offsets[start_line]
        end = offsets[end_line] if end_line < len(lines) else len(text)
        raw = text[start:end]
        signature = hashlib.sha256(raw.encode()).hexdigest()
        key = (parent_id, kind, signature)
        occurrences[key] = occurrences.get(key, 0) + 1
        block_id = readable_id or stable_source_id(
            (*key, occurrences[key]), prefix="block", digest_bytes=12
        )
        blocks.append(
            ParsedBlock(
                block_id=block_id,
                kind=kind,
                text=raw,
                raw=raw,
                parent_id=parent_id,
                start=start,
                end=end,
                cells=tuple(cells),
                metadata=metadata or {},
            )
        )

    index = 0
    paragraph_start: int | None = None

    def flush_paragraph(end_line: int) -> None:
        nonlocal paragraph_start
        if paragraph_start is not None:
            add_block(
                "paragraph",
                paragraph_start,
                end_line,
                parent_id=heading_ids[-1] if heading_ids else "",
            )
            paragraph_start = None

    while index < len(lines):
        line = lines[index]
        heading = _ATX.match(line)
        fence = _FENCE.match(line)
        if heading:
            flush_paragraph(index)
            level = len(heading.group(2))
            title = heading.group(3).strip()
            heading_path = heading_path[: level - 1]
            heading_ids = heading_ids[: level - 1]
            heading_path.append(_slug(title))
            base = "/".join(heading_path)
            existing = sum(
                block.block_id == base or block.block_id.startswith(f"{base}-")
                for block in blocks
            )
            block_id = base if not existing else f"{base}-{existing + 1}"
            add_block(
                "heading",
                index,
                index + 1,
                parent_id=heading_ids[-1] if heading_ids else "",
                metadata={"level": level, "title": title},
                readable_id=block_id,
            )
            heading_ids.append(block_id)
            index += 1
            continue
        if fence:
            flush_paragraph(index)
            marker = fence.group(1)
            end = index + 1
            closed = False
            while end < len(lines):
                candidate = lines[end].rstrip("\r\n")
                indentation = len(candidate) - len(candidate.lstrip(" "))
                stripped = candidate.lstrip(" ")
                run = len(stripped) - len(stripped.lstrip(marker[0]))
                if indentation <= 3 and run >= len(marker) and not stripped[run:].strip():
                    end += 1
                    closed = True
                    break
                end += 1
            if not closed:
                issues.append(
                    ParseIssue(
                        code="unclosed_fence",
                        message="fenced code block reaches end of source",
                        severity=(
                            ParseIssueSeverity.WARNING
                            if recover_unclosed_fences
                            else ParseIssueSeverity.ERROR
                        ),
                        start=offsets[index],
                        end=len(text),
                    )
                )
            add_block(
                "code",
                index,
                end,
                parent_id=heading_ids[-1] if heading_ids else "",
                metadata={"info": fence.group(2).strip()},
            )
            index = end
            continue
        if (
            tables
            and index + 1 < len(lines)
            and "|" in line
            and _TABLE_DIVIDER.match(lines[index + 1].rstrip("\r\n"))
        ):
            flush_paragraph(index)
            end = index + 2
            while end < len(lines) and "|" in lines[end] and lines[end].strip():
                end += 1
            rows = (_table_values(line),) + tuple(
                _table_values(value) for value in lines[index + 2 : end]
            )
            width = max(map(len, rows), default=0)
            cells = tuple(
                TableCell(row=row, column=column, text=value, header=row == 0)
                for row, values in enumerate(rows)
                for column, value in enumerate(values)
            )
            if any(len(values) != width for values in rows):
                issues.append(
                    ParseIssue(
                        code="ragged_table",
                        message="Markdown table rows have different cell counts",
                        severity=ParseIssueSeverity.WARNING,
                        start=offsets[index],
                        end=offsets[end] if end < len(lines) else len(text),
                    )
                )
            add_block(
                "table",
                index,
                end,
                parent_id=heading_ids[-1] if heading_ids else "",
                cells=cells,
                metadata={"columns": width},
            )
            index = end
            continue
        if not line.strip():
            flush_paragraph(index)
            index += 1
            continue
        if paragraph_start is None:
            paragraph_start = index
        index += 1
    flush_paragraph(len(lines))
    document = ParsedDocument(
        artifact_id=artifact_id,
        revision=revision,
        media_type="text/markdown",
        blocks=tuple(blocks),
    )
    return ParseResult(
        values=(document,),
        issues=tuple(issues),
        parser=parser_id,
        source_revision=revision,
        metadata={"tables": tables},
    )
