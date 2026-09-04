from __future__ import annotations

from mari_components import KnowledgeDocument, PollPage
from mari_components.connectors import validate_hint_hydration
from mari_components.documents import (
    BoundingBox,
    DocumentRegion,
    ParsedBlock,
    ParsedDocument,
    RegionEvidence,
    RegionKind,
    SourceCoordinateMap,
    StructuredDocument,
    TableCell,
    normalize_table,
    parse_delimited,
    parse_html,
    parse_json_array,
    parse_json_lines,
    parse_markdown,
    parse_python,
    stable_source_id,
    validate_parsed_document,
    validate_region_evidence,
    validate_structured_document,
)
from mari_components.schema import (
    ConceptType,
    KnowledgeSchema,
    PropertyConstraint,
    SemanticRecord,
    validate_records,
)
from mari_components.types import ChangeHint


def test_markdown_parser_preserves_spans_tables_and_stable_blocks() -> None:
    source = "# Policy\n\n| Rule | Days |\n|---|---:|\n| Return | 14 |\n\nText.\n"
    result = parse_markdown(source, artifact_id="policy", revision="1")
    document = result.values[0]
    assert result.succeeded
    assert all(
        source[block.start : block.end] == block.text for block in document.blocks
    )
    table = next(block for block in document.blocks if block.kind == "table")
    assert tuple((cell.row, cell.column, cell.text) for cell in table.cells) == (
        (0, 0, "Rule"),
        (0, 1, "Days"),
        (1, 0, "Return"),
        (1, 1, "14"),
    )
    shifted = parse_markdown(
        "Preamble.\n\n" + source, artifact_id="policy", revision="2"
    ).values[0]
    assert {block.block_id for block in document.blocks} <= {
        block.block_id for block in shifted.blocks
    }
    assert validate_parsed_document(document, source_length=len(source)).conforms
    assert any(
        item.code == "outside_parent_span"
        for item in validate_parsed_document(
            document,
            source_length=len(source),
            require_parent_span_containment=True,
        ).violations
    )


def test_source_coordinate_map_rejects_mid_character_byte_offsets() -> None:
    mapping = SourceCoordinateMap.build("aéz")
    assert mapping.to_byte(2) == 3
    assert mapping.to_character(3) == 2
    utf16 = SourceCoordinateMap.build("ab", encoding="utf-16")
    assert utf16.byte_length == len("ab".encode("utf-16")) == 6
    assert utf16.character_to_byte == (2, 4, 6)
    try:
        mapping.to_character(2)
    except ValueError as error:
        assert "character boundary" in str(error)
    else:
        raise AssertionError("mid-codepoint byte offset was accepted")


def test_html_parser_retains_visible_blocks_raw_spans_and_table_topology() -> None:
    source = (
        '<section id="rules"><h2>Rules &amp; limits</h2>'
        "<table><tr><th>Rule</th><th>Days</th></tr>"
        "<tr><td>Return</td><td>14</td></tr></table></section>"
    )
    result = parse_html(source, artifact_id="policy", revision="1")
    assert result.succeeded
    heading = next(
        block for block in result.values[0].blocks if block.kind == "heading"
    )
    assert heading.text == "Rules & limits"
    assert source[heading.start : heading.end].startswith("<h2>")
    table = next(block for block in result.values[0].blocks if block.kind == "table")
    assert table.text == "Rule Days Return 14"
    assert normalize_table(table.cells).rows == (
        ("Rule", "Days"),
        ("Return", "14"),
    )
    malformed = parse_html(
        "<table><tr><td>x", artifact_id="x", revision="1", recover=False
    )
    assert not malformed.succeeded


def test_structural_reports_expose_cycles_cells_and_evidence_mismatches() -> None:
    parsed = ParsedDocument(
        artifact_id="x",
        revision="1",
        media_type="text/plain",
        blocks=(
            ParsedBlock(block_id="a", kind="p", text="a", parent_id="b"),
            ParsedBlock(block_id="b", kind="p", text="b", parent_id="a"),
        ),
    )
    assert {item.code for item in validate_parsed_document(parsed).violations} == {
        "parent_cycle"
    }
    table = DocumentRegion(
        region_id="t",
        page=1,
        kind=RegionKind.TABLE,
        bbox=BoundingBox(left=0, top=0, right=10, bottom=10),
        cells=(
            TableCell(row=0, column=0, row_span=2, text="A"),
            TableCell(row=1, column=0, text="B"),
        ),
        parent_id="missing",
    )
    document = StructuredDocument(document_id="d", revision="1", regions=(table,))
    report = validate_structured_document(document)
    assert {item.code for item in report.violations} == {
        "missing_parent",
        "overlapping_table_cells",
    }
    assert normalize_table(table.cells).conflicts == ((1, 0),)
    assert normalize_table(table.cells, overlap="last").rows[1][0] == "B"
    try:
        normalize_table(table.cells, overlap="error")
    except ValueError as error:
        assert "overlap" in str(error)
    else:
        raise AssertionError("overlapping table was accepted in error mode")
    try:
        normalize_table((TableCell(row=100, column=100, text="x"),), maximum_cells=100)
    except ValueError as error:
        assert "maximum_cells" in str(error)
    else:
        raise AssertionError("oversized dense table was allocated")
    evidence = RegionEvidence(
        document_id="d", revision="2", region_id="t", page=2, cell=(4, 4)
    )
    resolution = validate_region_evidence(evidence, document)
    assert resolution.issues == (
        "revision_mismatch",
        "page_mismatch",
        "cell_not_found",
    )
    valid = validate_region_evidence(
        RegionEvidence(
            document_id="d", revision="1", region_id="t", page=1, cell=(0, 0)
        ),
        document,
    )
    assert valid.text == "A"
    ambiguous = validate_region_evidence(
        RegionEvidence(
            document_id="d", revision="1", region_id="t", page=1, cell=(1, 0)
        ),
        document,
    )
    assert ambiguous.issues == ("ambiguous_cell",)
    assert ambiguous.cell is None
    assert len(ambiguous.candidate_cells) == 2
    assert ambiguous.text == ""


def test_record_parsers_keep_good_siblings_and_raw_field_spans() -> None:
    csv_text = 'id,name\n1,"Ana, Rivera"\n2,Bao\n3\n'
    csv_result = parse_delimited(
        csv_text,
        source_id="people",
        revision="1",
        identity_fields=("id",),
    )
    assert len(csv_result.values) == 2
    assert csv_result.issues[0].code == "row_width_mismatch"
    name = csv_result.values[0].fields[1]
    assert csv_text[name.start : name.end] == '"Ana, Rivera"'
    json_text = '{"id":1,"name":"Ana"}\nnot-json\n{"id":2,"name":"Bao"}\n'
    json_result = parse_json_lines(
        json_text, source_id="people", revision="1", identity_fields=("id",)
    )
    assert len(json_result.values) == 2
    assert json_result.issues[0].code == "invalid_json_record"
    assert json_result.values[0].fields[1].raw == '"Ana"'
    assert stable_source_id(("people", 1)) == stable_source_id(("people", 1))
    assert stable_source_id((1,)) != stable_source_id(("1",))
    assert stable_source_id(({"a": 1, "b": 2},)) == stable_source_id(
        ({"b": 2, "a": 1},)
    )
    array = parse_json_array(
        '[{"id": 1, "name": "Ana"}, 4, {"id": 2, "name": "Bao"}]',
        source_id="people",
        revision="1",
        identity_fields=("id",),
    )
    assert len(array.values) == 2
    assert array.issues[0].code == "non_object_record"
    assert array.values[0].fields[1].raw == '"Ana"'
    assert (
        parse_json_array('[{"id": 1},]', source_id="people", revision="1")
        .issues[0]
        .code
        == "trailing_array_comma"
    )


def test_python_parser_preserves_unicode_offsets_identity_and_call_ambiguity() -> None:
    source = 'label = "é"\n\ndef helper():\n    return 1\n\ndef run():\n    return helper()\n'
    result = parse_python(source, repository="repo", revision="1", path="src/app.py")
    helper = next(
        symbol for symbol in result.symbols if symbol.qualified_name.endswith("helper")
    )
    assert source[helper.start : helper.end].startswith("def helper")
    assert any(edge.kind == "calls" for edge in result.edges)
    moved = parse_python(
        "# moved\n" + source, repository="repo", revision="2", path="src/app.py"
    )
    assert {symbol.symbol_id for symbol in result.symbols} == {
        symbol.symbol_id for symbol in moved.symbols
    }
    malformed = parse_python(
        "def broken(:\n", repository="repo", revision="3", path="x.py"
    )
    assert malformed.issues[0].code == "syntax_error"
    duplicate = parse_python(
        "def same(): pass\ndef same(): pass\ndef run(): same()\n",
        repository="repo",
        revision="1",
        path="same.py",
    )
    ids = [symbol.symbol_id for symbol in duplicate.symbols]
    assert len(ids) == len(set(ids))
    assert ids[-2].endswith("#2")
    ambiguous = next(
        reference for reference in duplicate.references if reference.name == "same"
    )
    assert len(ambiguous.resolved_target_ids) == 2
    assert all("::same.py" not in target for target in ambiguous.resolved_target_ids)


def test_schema_closed_properties_types_dates_and_duplicate_ids() -> None:
    schema = KnowledgeSchema(
        schema_id="policy",
        version="1",
        concepts=(ConceptType("Clause"),),
        properties=(
            PropertyConstraint("Clause", "days", value_type="integer"),
            PropertyConstraint(
                "Clause", "effective", value_type="string", value_format="date"
            ),
        ),
        allow_unknown_properties=False,
    )
    records = (
        SemanticRecord(
            record_id="a",
            concept="Clause",
            properties={"days": "14", "effective": "tomorrow", "extra": True},
        ),
        SemanticRecord(record_id="a", concept="Clause"),
    )
    report = validate_records(schema, records)
    assert {item.constraint_id for item in report.violations} == {
        "unique_record_id",
        "property:Clause:days:type",
        "property:Clause:effective:type",
        "closed_properties:Clause",
    }


def test_hint_hydration_reports_revision_and_identity_mismatch() -> None:
    hint = ChangeHint(
        provider="custom",
        aggregate_key="item:1",
        event_type="updated",
        external_id="1",
        revision="2",
    )
    page = PollPage(
        upserts=(
            KnowledgeDocument(
                source_id="custom",
                external_id="other",
                title="Other",
                body="stale",
                revision="1",
            ),
        ),
        snapshot_complete=True,
    )
    assert {item.reason for item in validate_hint_hydration(hint, (page,)).issues} == {
        "revision_mismatch",
        "external_id_mismatch",
    }
    custom = validate_hint_hydration(
        hint,
        (page,),
        revision_matches=lambda _hinted, _observed: True,
        external_id_matches=lambda _hinted, _observed: True,
    )
    assert custom.valid
