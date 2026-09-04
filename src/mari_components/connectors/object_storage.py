"""SDK-neutral batch ingestion for S3, GCS, Azure Blob, and compatible stores."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field

from mari_components.json import freeze_json_mapping
from mari_components.types import (
    KnowledgeDocument,
    PollPage,
    PollRequest,
    Tombstone,
    content_revision,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectStoreConfig:
    provider: str
    container: str
    prefix: str = ""

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.container.strip():
            raise ValueError("object-store provider and container are required")


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceObject:
    key: str
    revision: str
    updated_at: str = ""
    source_url: str = ""
    deleted: bool = False
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.key.strip() or not self.revision.strip():
            raise ValueError("source-object key and revision are required")
        object.__setattr__(self, "metadata", freeze_json_mapping(self.metadata))


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectListing:
    objects: tuple[SourceObject, ...]
    next_cursor: str | None = None
    complete: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "objects", tuple(self.objects))
        if not self.complete and not self.next_cursor:
            raise ValueError("incomplete object listing requires a next cursor")


ListObjects = Callable[[ObjectStoreConfig, str | None, int], ObjectListing]
ReadObject = Callable[[ObjectStoreConfig, SourceObject], bytes]


def poll_object_store(
    config: ObjectStoreConfig,
    request: PollRequest,
    *,
    list_objects: ListObjects,
    read_object: ReadObject,
    maximum_bytes: int = 5_242_880,
) -> Iterator[PollPage]:
    """Page an injected object-store SDK and normalize immutable objects.

    SDK authentication, signing, and retries remain application-owned. Mari
    owns bounded reads, document identity, tombstones, and checkpoint output.
    """

    if maximum_bytes < 1:
        raise ValueError("maximum_bytes must be positive")
    cursor = request.checkpoint or request.cursor
    for _ in range(request.page_limit):
        listing = list_objects(config, cursor, request.page_size)
        if len(listing.objects) > request.page_size:
            raise ValueError("object listing exceeds requested page size")
        documents: list[KnowledgeDocument] = []
        tombstones: list[Tombstone] = []
        source_id = f"{config.provider}:{config.container}"
        for item in listing.objects:
            if config.prefix and not item.key.startswith(config.prefix):
                raise ValueError("object listing escaped the configured prefix")
            if item.deleted:
                tombstones.append(Tombstone(source_id=source_id, external_id=item.key))
                continue
            raw = read_object(config, item)
            if len(raw) > maximum_bytes:
                raise ValueError(f"object {item.key!r} exceeds maximum_bytes")
            body = raw.decode("utf-8", "replace")
            documents.append(
                KnowledgeDocument(
                    source_id=source_id,
                    external_id=item.key,
                    title=item.key.rsplit("/", 1)[-1],
                    body=body,
                    revision=content_revision(body),
                    provider_revision=item.revision,
                    updated_at=item.updated_at,
                    source_url=item.source_url,
                    metadata={"container": config.container, **item.metadata},
                )
            )
        yield PollPage(
            upserts=tuple(documents),
            tombstones=tuple(tombstones),
            next_cursor=listing.next_cursor if listing.complete else request.cursor,
            next_checkpoint=None if listing.complete else listing.next_cursor,
            snapshot_complete=listing.complete,
        )
        if listing.complete:
            return
        if not listing.next_cursor or listing.next_cursor == cursor:
            raise ValueError("incomplete object listing requires a new cursor")
        cursor = listing.next_cursor
    yield PollPage(
        next_cursor=request.cursor,
        next_checkpoint=cursor,
        snapshot_complete=False,
        provider_metadata={"reason": "page_limit"},
    )
