"""Delimited and JSON Lines records with exact source coordinates."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Mapping

from . import ParsedField, ParsedRecord
from .results import ParseIssue, ParseIssueSeverity, ParseResult, stable_source_id


def _identity(
    values: Mapping[str, object], identity_fields: tuple[str, ...], fallback: int
) -> tuple[object, ...]:
    return (
        tuple(values.get(name) for name in identity_fields)
        if identity_fields
        else ("source_row", fallback)
    )


def _csv_spans(raw: str, *, delimiter: str, quotechar: str) -> tuple[tuple[int, int], ...]:
    spans: list[tuple[int, int]] = []
    start = 0
    quoted = False
    index = 0
    while index < len(raw):
        character = raw[index]
        if character == quotechar:
            if quoted and index + 1 < len(raw) and raw[index + 1] == quotechar:
                index += 2
                continue
            quoted = not quoted
        elif character == delimiter and not quoted:
            spans.append((start, index))
            start = index + 1
        index += 1
    spans.append((start, len(raw.rstrip("\r\n"))))
    return tuple(spans)


def parse_delimited(
    text: str,
    *,
    source_id: str,
    revision: str,
    identity_fields: Iterable[str] = (),
    delimiter: str | None = None,
    quotechar: str = '"',
    has_header: bool = True,
    strict_width: bool = True,
    parser_id: str = "mari.delimited@1",
) -> ParseResult[ParsedRecord]:
    """Parse CSV-like records and retain record and raw field spans."""

    if len(quotechar) != 1:
        raise ValueError("quotechar must be one character")
    if delimiter is None:
        try:
            delimiter = csv.Sniffer().sniff(text[:8192]).delimiter
        except csv.Error:
            delimiter = ","
    if len(delimiter) != 1:
        raise ValueError("delimiter must be one character")
    identity_names = tuple(identity_fields)
    physical = text.splitlines(keepends=True)
    starts: list[int] = []
    total = 0
    for line in physical:
        starts.append(total)
        total += len(line)
    reader = csv.reader(
        io.StringIO(text), delimiter=delimiter, quotechar=quotechar, strict=True
    )
    rows: list[tuple[list[str], int, int]] = []
    issues: list[ParseIssue] = []
    prior_line = 0
    try:
        for row in reader:
            end_line = reader.line_num
            start = starts[prior_line] if prior_line < len(starts) else len(text)
            end = starts[end_line] if end_line < len(starts) else len(text)
            rows.append((row, start, end))
            prior_line = end_line
    except csv.Error as error:
        start = starts[prior_line] if prior_line < len(starts) else len(text)
        issues.append(
            ParseIssue(
                code="invalid_delimited_record",
                message=str(error),
                start=start,
                end=len(text),
            )
        )
    if not rows:
        return ParseResult(
            values=(), issues=tuple(issues), parser=parser_id, source_revision=revision
        )
    if has_header:
        headers = tuple(rows[0][0])
        data = rows[1:]
        if len(headers) != len(set(headers)) or any(not value for value in headers):
            issues.append(
                ParseIssue(code="invalid_header", message="headers must be non-empty and unique")
            )
    else:
        width = len(rows[0][0])
        headers = tuple(f"column_{index + 1}" for index in range(width))
        data = rows
    records: list[ParsedRecord] = []
    for number, (row, start, end) in enumerate(data, 1):
        if len(row) != len(headers):
            issues.append(
                ParseIssue(
                    code="row_width_mismatch",
                    message=f"expected {len(headers)} fields, observed {len(row)}",
                    severity=(
                        ParseIssueSeverity.ERROR
                        if strict_width
                        else ParseIssueSeverity.WARNING
                    ),
                    subject=number,
                    start=start,
                    end=end,
                )
            )
            if strict_width:
                continue
        values = dict(zip(headers, row, strict=False))
        raw = text[start:end]
        spans = _csv_spans(raw, delimiter=delimiter, quotechar=quotechar)
        fields = tuple(
            ParsedField(
                name=name,
                value=value,
                raw=raw[field_start:field_end],
                start=start + field_start,
                end=start + field_end,
            )
            for (name, value), (field_start, field_end) in zip(
                values.items(), spans, strict=False
            )
        )
        records.append(
            ParsedRecord(
                record_id=stable_source_id(
                    (source_id, *_identity(values, identity_names, number)),
                    prefix="record",
                ),
                fields=fields,
                start=start,
                end=end,
            )
        )
    return ParseResult(
        values=tuple(records),
        issues=tuple(issues),
        parser=parser_id,
        source_revision=revision,
        metadata={
            "delimiter": delimiter,
            "has_header": has_header,
            "identity_fields": identity_names,
            "headers": headers,
        },
    )


def _top_level_field_spans(raw: str) -> dict[str, tuple[int, int]]:
    decoder = json.JSONDecoder()
    result: dict[str, tuple[int, int]] = {}
    index = 1
    while index < len(raw):
        while index < len(raw) and raw[index] in " \t\r\n,":
            index += 1
        if index >= len(raw) or raw[index] == "}":
            break
        key, key_end = decoder.raw_decode(raw, index)
        if not isinstance(key, str):
            break
        index = key_end
        while index < len(raw) and raw[index].isspace():
            index += 1
        if index >= len(raw) or raw[index] != ":":
            break
        index += 1
        while index < len(raw) and raw[index].isspace():
            index += 1
        start = index
        _, end = decoder.raw_decode(raw, index)
        result[key] = (start, end)
        index = end
    return result


def parse_json_lines(
    text: str,
    *,
    source_id: str,
    revision: str,
    identity_fields: Iterable[str] = (),
    parser_id: str = "mari.jsonl@1",
) -> ParseResult[ParsedRecord]:
    """Parse JSON objects independently so malformed siblings do not disappear."""

    identity_names = tuple(identity_fields)
    records: list[ParsedRecord] = []
    issues: list[ParseIssue] = []
    offset = 0
    for number, line in enumerate(text.splitlines(keepends=True), 1):
        raw = line.rstrip("\r\n")
        start = offset
        end = start + len(raw)
        offset += len(line)
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as error:
            issues.append(
                ParseIssue(
                    code="invalid_json_record",
                    message=error.msg,
                    subject=number,
                    start=start + error.pos,
                    end=min(end, start + error.pos + 1),
                )
            )
            continue
        if not isinstance(value, dict):
            issues.append(
                ParseIssue(
                    code="non_object_record",
                    message="JSON Lines records must be objects",
                    subject=number,
                    start=start,
                    end=end,
                )
            )
            continue
        spans = _top_level_field_spans(raw)
        fields = tuple(
            ParsedField(
                name=name,
                value=field_value,
                raw=raw[spans[name][0] : spans[name][1]],
                start=start + spans[name][0],
                end=start + spans[name][1],
            )
            for name, field_value in value.items()
            if name in spans
        )
        records.append(
            ParsedRecord(
                record_id=stable_source_id(
                    (source_id, *_identity(value, identity_names, number)),
                    prefix="record",
                ),
                fields=fields,
                start=start,
                end=end,
            )
        )
    return ParseResult(
        values=tuple(records),
        issues=tuple(issues),
        parser=parser_id,
        source_revision=revision,
        metadata={"identity_fields": identity_names},
    )


def parse_json_array(
    text: str,
    *,
    source_id: str,
    revision: str,
    identity_fields: Iterable[str] = (),
    parser_id: str = "mari.json-array@1",
) -> ParseResult[ParsedRecord]:
    """Parse top-level array objects with exact record and field spans."""

    identity_names = tuple(identity_fields)
    decoder = json.JSONDecoder()
    records: list[ParsedRecord] = []
    issues: list[ParseIssue] = []
    index = 0
    while index < len(text) and text[index].isspace():
        index += 1
    if index >= len(text) or text[index] != "[":
        return ParseResult(
            values=(),
            issues=(
                ParseIssue(
                    code="array_required",
                    message="top-level JSON value must be an array",
                    start=index,
                    end=min(len(text), index + 1),
                ),
            ),
            parser=parser_id,
            source_revision=revision,
        )
    index += 1
    number = 0
    while True:
        while index < len(text) and text[index].isspace():
            index += 1
        if index < len(text) and text[index] == "]":
            index += 1
            while index < len(text) and text[index].isspace():
                index += 1
            if index < len(text):
                issues.append(
                    ParseIssue(
                        code="trailing_json_content",
                        message="content follows the top-level JSON array",
                        start=index,
                        end=len(text),
                    )
                )
            break
        if index >= len(text):
            issues.append(
                ParseIssue(
                    code="unterminated_array",
                    message="JSON array has no closing bracket",
                    start=max(0, len(text) - 1),
                    end=len(text),
                )
            )
            break
        start = index
        try:
            value, end = decoder.raw_decode(text, index)
        except json.JSONDecodeError as error:
            issues.append(
                ParseIssue(
                    code="invalid_json_record",
                    message=error.msg,
                    subject=number + 1,
                    start=error.pos,
                    end=min(len(text), error.pos + 1),
                )
            )
            break
        number += 1
        if not isinstance(value, dict):
            issues.append(
                ParseIssue(
                    code="non_object_record",
                    message="JSON array members must be objects",
                    subject=number,
                    start=start,
                    end=end,
                )
            )
        else:
            raw = text[start:end]
            spans = _top_level_field_spans(raw)
            fields = tuple(
                ParsedField(
                    name=name,
                    value=field_value,
                    raw=raw[spans[name][0] : spans[name][1]],
                    start=start + spans[name][0],
                    end=start + spans[name][1],
                )
                for name, field_value in value.items()
                if name in spans
            )
            records.append(
                ParsedRecord(
                    record_id=stable_source_id(
                        (source_id, *_identity(value, identity_names, number)),
                        prefix="record",
                    ),
                    fields=fields,
                    start=start,
                    end=end,
                )
            )
        index = end
        while index < len(text) and text[index].isspace():
            index += 1
        if index < len(text) and text[index] == ",":
            index += 1
            check = index
            while check < len(text) and text[check].isspace():
                check += 1
            if check < len(text) and text[check] == "]":
                issues.append(
                    ParseIssue(
                        code="trailing_array_comma",
                        message="JSON arrays cannot end with a comma",
                        start=index - 1,
                        end=index,
                    )
                )
                break
            continue
        if index < len(text) and text[index] == "]":
            index += 1
            while index < len(text) and text[index].isspace():
                index += 1
            if index < len(text):
                issues.append(
                    ParseIssue(
                        code="trailing_json_content",
                        message="content follows the top-level JSON array",
                        start=index,
                        end=len(text),
                    )
                )
            break
        if index < len(text):
            issues.append(
                ParseIssue(
                    code="array_separator_required",
                    message="JSON array members must be comma-separated",
                    start=index,
                    end=index + 1,
                )
            )
            break
    return ParseResult(
        values=tuple(records),
        issues=tuple(issues),
        parser=parser_id,
        source_revision=revision,
        metadata={"identity_fields": identity_names},
    )
