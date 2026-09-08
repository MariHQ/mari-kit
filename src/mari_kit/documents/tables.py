"""Table topology normalization without format or domain assumptions."""

from __future__ import annotations

from dataclasses import dataclass

from . import TableCell


@dataclass(frozen=True, slots=True, kw_only=True)
class NormalizedTable:
    rows: tuple[tuple[str | None, ...], ...]
    source_cells: tuple[tuple[tuple[int, int] | None, ...], ...]
    conflicts: tuple[tuple[int, int], ...]


def normalize_table(
    cells: tuple[TableCell, ...],
    *,
    maximum_cells: int = 1_000_000,
    overlap: str = "first",
) -> NormalizedTable:
    """Expand row/column spans and report overlapping source cells."""

    if maximum_cells < 1:
        raise ValueError("maximum_cells must be positive")
    if overlap not in {"first", "last", "error"}:
        raise ValueError("overlap must be first, last, or error")
    height = max((cell.row + cell.row_span for cell in cells), default=0)
    width = max((cell.column + cell.column_span for cell in cells), default=0)
    if height * width > maximum_cells:
        raise ValueError("expanded table exceeds maximum_cells")
    values: list[list[str | None]] = [[None] * width for _ in range(height)]
    sources: list[list[tuple[int, int] | None]] = [
        [None] * width for _ in range(height)
    ]
    conflicts: set[tuple[int, int]] = set()
    for cell in cells:
        source = (cell.row, cell.column)
        for row in range(cell.row, cell.row + cell.row_span):
            for column in range(cell.column, cell.column + cell.column_span):
                if sources[row][column] is not None:
                    conflicts.add((row, column))
                    if overlap == "error":
                        raise ValueError(f"table cells overlap at ({row}, {column})")
                    if overlap == "first":
                        continue
                values[row][column] = cell.text
                sources[row][column] = source
    return NormalizedTable(
        rows=tuple(tuple(row) for row in values),
        source_cells=tuple(tuple(row) for row in sources),
        conflicts=tuple(sorted(conflicts)),
    )
