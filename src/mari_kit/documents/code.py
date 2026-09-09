"""Concrete, dependency-free Python structure extraction."""

from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass
from itertools import chain

from . import CodeEdge, CodeEdgeKind, CodeReference, CodeSymbol, CodeSymbolKind
from .coordinates import SourceCoordinateMap
from .results import ParseIssue


@dataclass(frozen=True, slots=True, kw_only=True)
class CodeParseResult:
    symbols: tuple[CodeSymbol, ...]
    edges: tuple[CodeEdge, ...]
    references: tuple[CodeReference, ...]
    issues: tuple[ParseIssue, ...]
    parser: str
    coordinate_unit: str = "character"

    @property
    def succeeded(self) -> bool:
        return not self.issues


def _line_starts(source: str) -> tuple[int, ...]:
    values = [0]
    for index, character in enumerate(source):
        if character == "\n":
            values.append(index + 1)
    return tuple(values)


def _character_offset(
    lines: tuple[str, ...], starts: tuple[int, ...], line: int, byte_column: int
) -> int:
    content = lines[line - 1]
    mapping = SourceCoordinateMap.build(content)
    character_column = mapping.to_character(byte_column)
    return starts[line - 1] + character_column


def parse_python(
    source: str,
    *,
    repository: str,
    revision: str,
    path: str,
    parser_id: str = "python.ast@stdlib",
) -> CodeParseResult:
    """Extract definitions and local call references with stable qualified IDs."""

    if not repository.strip() or not revision.strip() or not path.strip():
        raise ValueError("repository, revision, and path are required")
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as error:
        lines = source.splitlines(keepends=True)
        starts = _line_starts(source)
        start = None
        end = None
        if error.lineno and error.offset and error.lineno <= len(lines):
            start = starts[error.lineno - 1] + max(0, error.offset - 1)
            end = min(len(source), start + 1)
        return CodeParseResult(
            symbols=(),
            edges=(),
            references=(),
            issues=(
                ParseIssue(
                    code="syntax_error",
                    message=error.msg,
                    start=start,
                    end=end,
                ),
            ),
            parser=parser_id,
        )

    lines = tuple(source.splitlines(keepends=True))
    starts = _line_starts(source)
    symbols: list[CodeSymbol] = []
    edges: list[CodeEdge] = []
    nodes: list[tuple[ast.AST, CodeSymbol]] = []
    module_name = path.rsplit(".", 1)[0].replace("/", ".")
    module_id = f"{repository}:{path}::{module_name}"
    module = CodeSymbol(
        symbol_id=module_id,
        repository=repository,
        revision=revision,
        language="python",
        qualified_name=module_name,
        kind=CodeSymbolKind.MODULE,
        start_line=1,
        end_line=max(1, len(lines)),
        path=path,
        start=0,
        end=len(source),
        content_revision=hashlib.sha256(source.encode()).hexdigest(),
    )
    symbols.append(module)
    symbol_occurrences: dict[str, int] = {}

    def visit_definitions(node: ast.AST, parent: CodeSymbol) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified = f"{parent.qualified_name}.{child.name}"
                base_id = f"{repository}:{path}::{qualified}"
                symbol_occurrences[base_id] = symbol_occurrences.get(base_id, 0) + 1
                occurrence = symbol_occurrences[base_id]
                symbol_id = base_id if occurrence == 1 else f"{base_id}#{occurrence}"
                start = _character_offset(lines, starts, child.lineno, child.col_offset)
                end_line = child.end_lineno or child.lineno
                end_column = child.end_col_offset or child.col_offset
                end = _character_offset(lines, starts, end_line, end_column)
                if isinstance(child, ast.ClassDef):
                    kind = CodeSymbolKind.CLASS
                elif parent.kind is CodeSymbolKind.CLASS:
                    kind = CodeSymbolKind.METHOD
                else:
                    kind = CodeSymbolKind.FUNCTION
                symbol = CodeSymbol(
                    symbol_id=symbol_id,
                    repository=repository,
                    revision=revision,
                    language="python",
                    qualified_name=qualified,
                    kind=kind,
                    start_line=child.lineno,
                    end_line=end_line,
                    path=path,
                    parent_id=parent.symbol_id,
                    start=start,
                    end=end,
                    content_revision=hashlib.sha256(
                        source[start:end].encode()
                    ).hexdigest(),
                )
                symbols.append(symbol)
                nodes.append((child, symbol))
                edges.append(
                    CodeEdge(
                        source_id=parent.symbol_id,
                        target_id=symbol.symbol_id,
                        kind=CodeEdgeKind.DEFINES,
                    )
                )
                visit_definitions(child, symbol)
            elif not isinstance(child, (ast.Lambda, ast.comprehension)):
                visit_definitions(child, parent)

    visit_definitions(tree, module)
    by_name: dict[str, list[str]] = {}
    for symbol in symbols:
        if symbol.kind is CodeSymbolKind.MODULE:
            continue
        by_name.setdefault(symbol.qualified_name.rsplit(".", 1)[-1], []).append(
            symbol.symbol_id
        )
    references: list[CodeReference] = []
    for node, owner in nodes:
        nested = {
            child
            for child in ast.walk(node)
            if child is not node
            and isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        }
        nested_nodes = set(chain.from_iterable(ast.walk(value) for value in nested))
        for child in ast.walk(node):
            if not isinstance(child, ast.Call) or child in nested_nodes:
                continue
            function = child.func
            name = (
                function.id
                if isinstance(function, ast.Name)
                else function.attr
                if isinstance(function, ast.Attribute)
                else ""
            )
            if not name:
                continue
            start = _character_offset(
                lines, starts, function.lineno, function.col_offset
            )
            end = _character_offset(
                lines,
                starts,
                function.end_lineno or function.lineno,
                function.end_col_offset or function.col_offset,
            )
            targets = tuple(sorted(by_name.get(name, ())))
            references.append(
                CodeReference(
                    source_id=owner.symbol_id,
                    name=name,
                    kind=CodeEdgeKind.CALLS,
                    start=start,
                    end=end,
                    resolved_target_ids=targets,
                )
            )
            if len(targets) == 1:
                edges.append(
                    CodeEdge(
                        source_id=owner.symbol_id,
                        target_id=targets[0],
                        kind=CodeEdgeKind.CALLS,
                    )
                )
    return CodeParseResult(
        symbols=tuple(symbols),
        edges=tuple(edges),
        references=tuple(references),
        issues=(),
        parser=parser_id,
    )
