"""Small HTML-to-block adapter with raw source spans and table topology."""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser

from . import ParsedBlock, ParsedDocument, TableCell
from .results import ParseIssue, ParseIssueSeverity, ParseResult, stable_source_id

_BLOCKS = {
    "h1": "heading",
    "h2": "heading",
    "h3": "heading",
    "h4": "heading",
    "h5": "heading",
    "h6": "heading",
    "p": "paragraph",
    "li": "list_item",
    "pre": "code",
    "blockquote": "quote",
    "table": "table",
}
_VOID = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "source",
    "track",
    "wbr",
}


@dataclass
class _Frame:
    tag: str
    start: int
    parent_block: int | None
    block: int | None
    attrs: dict[str, str]
    text: list[str] = field(default_factory=list)
    cells: list[TableCell] = field(default_factory=list)
    table_row: int = -1
    table_columns: dict[int, int] = field(default_factory=dict)
    cell_position: tuple[int, int] | None = None


@dataclass
class _Candidate:
    tag: str
    kind: str
    start: int
    end: int
    parent: int | None
    attrs: dict[str, str]
    text: str
    cells: tuple[TableCell, ...]


class _BlockParser(HTMLParser):
    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=True)
        self.source = source
        self.line_offsets = [0]
        for index, character in enumerate(source):
            if character == "\n":
                self.line_offsets.append(index + 1)
        self.stack: list[_Frame] = []
        self.candidates: list[_Candidate | None] = []
        self.issues: list[ParseIssue] = []

    def source_offset(self) -> int:
        line, column = self.getpos()
        return self.line_offsets[line - 1] + column

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        parent = next(
            (frame.block for frame in reversed(self.stack) if frame.block is not None),
            None,
        )
        block = len(self.candidates) if tag in _BLOCKS else None
        if block is not None:
            self.candidates.append(None)
        frame = _Frame(
            tag=tag,
            start=self.source_offset(),
            parent_block=parent,
            block=block,
            attrs={name.casefold(): value or "" for name, value in attrs},
        )
        if tag == "tr":
            table = next(
                (value for value in reversed(self.stack) if value.tag == "table"), None
            )
            if table is not None:
                table.table_row += 1
        if tag in {"th", "td"}:
            table = next(
                (value for value in reversed(self.stack) if value.tag == "table"), None
            )
            if table is not None:
                row = max(0, table.table_row)
                column = table.table_columns.get(row, 0)
                frame.cell_position = (row, column)
                try:
                    column_span = max(1, int(frame.attrs.get("colspan", "1")))
                    row_span = max(1, int(frame.attrs.get("rowspan", "1")))
                except ValueError:
                    column_span = row_span = 1
                    self.issues.append(
                        ParseIssue(
                            code="invalid_cell_span",
                            message="rowspan and colspan must be positive integers",
                            severity=ParseIssueSeverity.WARNING,
                            start=frame.start,
                            end=frame.start + len(self.get_starttag_text() or ""),
                        )
                    )
                frame.attrs["_rowspan"] = str(row_span)
                frame.attrs["_colspan"] = str(column_span)
                table.table_columns[row] = column + column_span
        if tag not in _VOID:
            self.stack.append(frame)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.casefold() not in _VOID:
            self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        for frame in self.stack:
            frame.text.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        match = next(
            (
                index
                for index in range(len(self.stack) - 1, -1, -1)
                if self.stack[index].tag == tag
            ),
            None,
        )
        if match is None:
            self.issues.append(
                ParseIssue(
                    code="unmatched_end_tag",
                    message=f"no open <{tag}> element",
                    severity=ParseIssueSeverity.WARNING,
                    start=self.source_offset(),
                    end=self.source_offset() + len(f"</{tag}>"),
                )
            )
            return
        end = self.source_offset() + len(f"</{tag}>")
        for frame in reversed(self.stack[match + 1 :]):
            self._finish(frame, self.source_offset(), unclosed=True)
        frame = self.stack[match]
        self._finish(frame, end, unclosed=False)
        del self.stack[match:]

    def _finish(self, frame: _Frame, end: int, *, unclosed: bool) -> None:
        if unclosed:
            self.issues.append(
                ParseIssue(
                    code="implicitly_closed_tag",
                    message=f"<{frame.tag}> closed by an ancestor end tag",
                    severity=ParseIssueSeverity.WARNING,
                    start=frame.start,
                    end=end,
                )
            )
        if frame.tag in {"th", "td"} and frame.cell_position is not None:
            table = next(
                (value for value in reversed(self.stack) if value.tag == "table"), None
            )
            if table is not None:
                row, column = frame.cell_position
                table.cells.append(
                    TableCell(
                        row=row,
                        column=column,
                        text=" ".join(" ".join(frame.text).split()),
                        row_span=int(frame.attrs["_rowspan"]),
                        column_span=int(frame.attrs["_colspan"]),
                        header=frame.tag == "th",
                    )
                )
        if frame.block is not None:
            self.candidates[frame.block] = _Candidate(
                tag=frame.tag,
                kind=_BLOCKS[frame.tag],
                start=frame.start,
                end=end,
                parent=frame.parent_block,
                attrs=frame.attrs,
                text=" ".join(" ".join(frame.text).split()),
                cells=tuple(frame.cells),
            )

    def finish(self) -> None:
        for frame in reversed(self.stack):
            self._finish(frame, len(self.source), unclosed=True)
        self.stack.clear()


def parse_html(
    source: str,
    *,
    artifact_id: str,
    revision: str,
    parser_id: str = "mari.html@1",
    recover: bool = True,
) -> ParseResult[ParsedDocument]:
    """Extract common HTML blocks and tables using character source offsets."""

    parser = _BlockParser(source)
    parser.feed(source)
    parser.close()
    parser.finish()
    issues = tuple(
        ParseIssue(
            code=issue.code,
            message=issue.message,
            severity=issue.severity if recover else ParseIssueSeverity.ERROR,
            subject=issue.subject,
            start=issue.start,
            end=issue.end,
        )
        for issue in parser.issues
    )
    occurrences: dict[str, int] = {}
    ids: dict[int, str] = {}
    for index, candidate in enumerate(parser.candidates):
        if candidate is None:
            continue
        explicit = candidate.attrs.get("id", "")
        base = (
            f"html:{explicit}"
            if explicit
            else stable_source_id(
                (candidate.tag, candidate.text), prefix="block", digest_bytes=12
            )
        )
        occurrences[base] = occurrences.get(base, 0) + 1
        ids[index] = base if occurrences[base] == 1 else f"{base}-{occurrences[base]}"
    blocks = tuple(
        ParsedBlock(
            block_id=ids[index],
            kind=candidate.kind,
            text=candidate.text,
            raw=source[candidate.start : candidate.end],
            parent_id="" if candidate.parent is None else ids.get(candidate.parent, ""),
            start=candidate.start,
            end=candidate.end,
            cells=candidate.cells,
            metadata={"tag": candidate.tag, "attributes": candidate.attrs},
        )
        for index, candidate in enumerate(parser.candidates)
        if candidate is not None
    )
    document = ParsedDocument(
        artifact_id=artifact_id,
        revision=revision,
        media_type="text/html",
        blocks=blocks,
    )
    return ParseResult(
        values=(document,),
        issues=issues,
        parser=parser_id,
        source_revision=revision,
        metadata={"block_tags": tuple(sorted(_BLOCKS)), "recover": recover},
    )
