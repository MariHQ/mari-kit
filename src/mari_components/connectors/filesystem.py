"""Stable, bounded local-filesystem batch ingestion."""

from __future__ import annotations

import fnmatch
import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from mari_components.connectors.protocol import ValidationResult
from mari_components.http import HttpTransport
from mari_components.types import (
    KnowledgeDocument,
    PollPage,
    PollRequest,
    content_revision,
)

DEFAULT_PATTERNS = ("*.md", "*.mdx", "*.rst", "*.adoc", "*.txt")


@dataclass(frozen=True, slots=True)
class FilesystemConfig:
    root: Path
    patterns: tuple[str, ...] = DEFAULT_PATTERNS
    recursive: bool = True
    source_name: str = "local"

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))
        if not self.patterns or not self.source_name.strip():
            raise ValueError("filesystem patterns and source name are required")


def validate_filesystem(
    config: FilesystemConfig, *, http: HttpTransport | None = None
) -> ValidationResult:
    root = config.root.resolve()
    if not root.is_dir():
        return ValidationResult(False, "filesystem root is not a readable directory")
    return ValidationResult(True, identity=str(root))


def _files(config: FilesystemConfig) -> tuple[tuple[Path, str, int, int], ...]:
    root = config.root.resolve()
    if not root.is_dir():
        raise ValueError("filesystem root is not a readable directory")
    paths = root.rglob("*") if config.recursive else root.glob("*")
    rows = []
    for path in paths:
        resolved = path.resolve()
        if not resolved.is_file() or not resolved.is_relative_to(root):
            continue
        relative = resolved.relative_to(root).as_posix()
        name = resolved.name
        if not any(
            fnmatch.fnmatch(relative, pattern) or fnmatch.fnmatch(name, pattern)
            for pattern in config.patterns
        ):
            continue
        stat = resolved.stat()
        rows.append((resolved, relative, stat.st_size, stat.st_mtime_ns))
    return tuple(sorted(rows, key=lambda row: row[1]))


def _snapshot(rows: tuple[tuple[Path, str, int, int], ...]) -> str:
    identity = "\0".join(
        f"{relative}\0{size}\0{modified}" for _path, relative, size, modified in rows
    )
    return hashlib.sha256(identity.encode()).hexdigest()


def _checkpoint(value: str | None) -> tuple[str, int]:
    if not value:
        return "", 0
    try:
        raw = json.loads(value)
        return str(raw["snapshot"]), int(raw["offset"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("invalid filesystem checkpoint") from error


def poll_filesystem(
    config: FilesystemConfig,
    request: PollRequest,
    *,
    http: HttpTransport | None = None,
    maximum_bytes: int = 5_242_880,
) -> Iterator[PollPage]:
    """Read a stable file listing; fail resume if the listing changed."""

    if maximum_bytes < 1:
        raise ValueError("maximum_bytes must be positive")
    rows = _files(config)
    snapshot = _snapshot(rows)
    checkpoint_snapshot, offset = _checkpoint(request.checkpoint)
    if checkpoint_snapshot and checkpoint_snapshot != snapshot:
        raise ValueError("filesystem changed while a batch checkpoint was active")
    if not request.checkpoint and request.cursor == snapshot:
        yield PollPage(next_cursor=snapshot, snapshot_complete=True)
        return
    for _ in range(request.page_limit):
        selected = rows[offset : offset + request.page_size]
        documents = []
        for path, relative, size, modified in selected:
            if size > maximum_bytes:
                continue
            raw = path.read_bytes()
            if len(raw) > maximum_bytes:
                raise ValueError(f"file {relative!r} exceeds maximum_bytes")
            revision = content_revision(raw)
            documents.append(
                KnowledgeDocument(
                    source_id=f"filesystem:{config.source_name}",
                    external_id=relative,
                    title=path.name,
                    body=raw.decode("utf-8", "replace"),
                    revision=revision,
                    metadata={"path": relative, "size": size, "modified_ns": modified},
                )
            )
        offset += len(selected)
        complete = offset >= len(rows)
        yield PollPage(
            upserts=tuple(documents),
            next_cursor=snapshot if complete else request.cursor,
            next_checkpoint=(
                None
                if complete
                else json.dumps(
                    {"snapshot": snapshot, "offset": offset},
                    sort_keys=True,
                    separators=(",", ":"),
                )
            ),
            snapshot_complete=complete,
        )
        if complete:
            return
    yield PollPage(
        next_cursor=request.cursor,
        next_checkpoint=json.dumps(
            {"snapshot": snapshot, "offset": offset},
            sort_keys=True,
            separators=(",", ":"),
        ),
        snapshot_complete=False,
        provider_metadata={"reason": "page_limit"},
    )
