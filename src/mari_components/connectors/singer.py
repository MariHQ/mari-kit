"""Singer/Meltano message adapter for batch connector interoperability."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Iterator, Mapping
from typing import Any

from mari_components.types import KnowledgeDocument, PollPage

SingerDocument = Callable[[str, Mapping[str, Any]], KnowledgeDocument | None]


def singer_pages(
    messages: Iterable[str | bytes | Mapping[str, Any]],
    *,
    document: SingerDocument,
    page_size: int = 100,
) -> Iterator[PollPage]:
    """Convert Singer RECORD/STATE messages to bounded Mari pages.

    The tap process and state persistence are host-owned. A Singer STATE value
    becomes Mari's next checkpoint only after preceding records are yielded.
    """

    if page_size < 1:
        raise ValueError("page_size must be positive")
    documents: list[KnowledgeDocument] = []
    checkpoint: str | None = None
    for raw in messages:
        if isinstance(raw, Mapping):
            message = dict(raw)
        else:
            try:
                message = json.loads(raw)
            except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError("Singer message must be a JSON object") from error
        if not isinstance(message, dict):
            raise ValueError("Singer message must be a JSON object")
        kind = str(message.get("type") or "").upper()
        if kind == "RECORD":
            stream = str(message.get("stream") or "")
            record = message.get("record")
            if not stream or not isinstance(record, dict):
                raise ValueError("Singer RECORD requires stream and object record")
            value = document(stream, record)
            if value is not None:
                documents.append(value)
            if len(documents) >= page_size:
                yield PollPage(upserts=tuple(documents), snapshot_complete=False)
                documents.clear()
        elif kind == "STATE":
            checkpoint = json.dumps(
                message.get("value"), sort_keys=True, separators=(",", ":")
            )
        elif kind not in {"SCHEMA", "ACTIVATE_VERSION", "BATCH"}:
            raise ValueError(f"unsupported Singer message type: {kind!r}")
    yield PollPage(
        upserts=tuple(documents),
        next_cursor=checkpoint,
        snapshot_complete=True,
    )
