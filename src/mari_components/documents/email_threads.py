"""Reconstruct email threads from headers, quoted text and subject evidence.

Standard library only. No filesystem or network access: the host parses the
messages and passes them in. Threading never trusts a single signal. Header
links come first, then quoted and forwarded fragments that reproduce another
message's own words, then verbatim containment, and finally a conservative
subject match that also needs a shared participant inside a time gap.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum

from mari_components.conversation_knowledge import KnowledgeEvent
from mari_components.documents.email import EmailMessage, Fragment, FragmentKind

NO_SUBJECT = "(no subject)"
_QUOTE_KINDS = frozenset({FragmentKind.QUOTED, FragmentKind.FORWARDED})
_SENDER_WINDOW_SECONDS = 120.0
_BUCKET_LIMIT = 64


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def _order(message: EmailMessage) -> tuple[float, str]:
    return (message.timestamp, message.message_id)


class LinkReason(StrEnum):
    HEADER = "header"
    QUOTED = "quoted"
    SUBSET = "subset"
    SUBJECT = "subject"


@dataclass(frozen=True, slots=True, kw_only=True)
class ThreadLink:
    """Why ``child_id`` was placed in the same thread as ``parent_id``."""

    child_id: str
    parent_id: str
    reason: LinkReason

    def __post_init__(self) -> None:
        if not self.child_id or not self.parent_id or self.child_id == self.parent_id:
            raise ValueError("thread link requires two distinct message IDs")


@dataclass(frozen=True, slots=True, kw_only=True)
class EmailThread:
    """One conversation. ``messages`` are real; ``reconstructed`` came from quotes."""

    thread_id: str
    messages: tuple[EmailMessage, ...]
    reconstructed: tuple[EmailMessage, ...] = ()
    duplicates: tuple[str, ...] = ()
    links: tuple[ThreadLink, ...] = ()

    def __post_init__(self) -> None:
        if not self.thread_id or not self.messages:
            raise ValueError("email thread identity and members are required")
        object.__setattr__(self, "messages", tuple(self.messages))
        object.__setattr__(self, "reconstructed", tuple(self.reconstructed))
        object.__setattr__(self, "duplicates", tuple(self.duplicates))
        object.__setattr__(self, "links", tuple(self.links))

    @property
    def subject(self) -> str:
        return self.messages[0].subject

    @property
    def participants(self) -> frozenset[str]:
        """Every address seen on real or reconstructed members."""
        addresses: set[str] = set()
        for message in (*self.messages, *self.reconstructed):
            addresses.update(message.participants)
        return frozenset(addresses)


class _Union:
    """Union-find with deterministic root choice (the smaller ID wins)."""

    def __init__(self, items: Iterable[str]) -> None:
        self._parent = {item: item for item in items}

    def __contains__(self, item: str) -> bool:
        return item in self._parent

    def find(self, item: str) -> str:
        root = item
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[item] != root:
            self._parent[item], item = root, self._parent[item]
        return root

    def union(self, left: str, right: str) -> None:
        first, second = self.find(left), self.find(right)
        if first != second:
            self._parent[max(first, second)] = min(first, second)


def _dedup(
    messages: Iterable[EmailMessage],
) -> tuple[dict[str, EmailMessage], list[tuple[str, str]], dict[str, str]]:
    """Drop repeated Message-IDs, then near-identical sends.

    Returns (kept, dropped pairs, alias). ``alias`` maps every dropped id to
    the kept id that stands in for it, so header references keep resolving.
    """
    dropped: list[tuple[str, str]] = []
    unique: list[EmailMessage] = []
    seen: set[str] = set()
    for message in messages:
        if message.message_id in seen:
            dropped.append((message.message_id, message.message_id))
            continue
        seen.add(message.message_id)
        unique.append(message)
    kept: dict[str, EmailMessage] = {}
    alias: dict[str, str] = {}
    fingerprints: dict[tuple[str, int, str], str] = {}
    for message in unique:
        digest = message.bulk.body_digest
        if digest:
            key = (message.sender, int(message.timestamp // 60), digest)
            original = fingerprints.get(key)
            if original is not None:
                dropped.append((message.message_id, original))
                alias[message.message_id] = original
                continue
            fingerprints[key] = message.message_id
        kept[message.message_id] = message
    return kept, dropped, alias


def _nearest(
    candidates: list[str], anchor: float, kept: dict[str, EmailMessage]
) -> list[str]:
    """Bound a candidate bucket to the entries closest in time, deterministically."""
    if len(candidates) <= _BUCKET_LIMIT:
        return candidates
    return sorted(
        candidates,
        key=lambda c: (abs(kept[c].timestamp - anchor), kept[c].timestamp, c),
    )[:_BUCKET_LIMIT]


def _prefix_related(left: str, right: str, minimum: int) -> bool:
    """True when the shorter text is a prefix of the longer and at least ``minimum`` long."""
    shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
    return len(shorter) >= minimum and longer.startswith(shorter)


def _sender_matches(candidate: EmailMessage, fragment: Fragment) -> bool:
    if not fragment.sender or not fragment.timestamp or not candidate.sender:
        return False
    return (
        candidate.sender.lower() in fragment.sender.lower()
        and abs(candidate.timestamp - fragment.timestamp) <= _SENDER_WINDOW_SECONDS
    )


def thread_emails(
    messages: Iterable[EmailMessage],
    *,
    gap_seconds: float = 14 * 86400,
    reconstruct: bool = True,
    minimum_match_characters: int = 200,
) -> tuple[EmailThread, ...]:
    """Group messages into threads; optionally recover quoted originals.

    Steps: dedup by Message-ID and by (sender, minute, body digest); union-find
    over header links, quoted fragments, verbatim containment and guarded
    subject matches; then reconstruct quoted originals that matched nothing.

    Cost: quoted and containment matching share one hash index keyed by the
    first ``minimum_match_characters`` characters of each normalized own text.
    A fragment costs one lookup; a body costs one lookup per character
    position, so both stay linear in total text size instead of all-pairs.
    A prefix hit is only a bucket: the full texts must then stand in a
    prefix relation (quoted) or be fully contained (subset). Every bucket is
    bounded to the 64 candidates nearest in time, and subject matching keeps
    at most the 64 latest anchors per subject inside ``gap_seconds``, so the
    worst case stays linear in message count times that constant.
    """
    if not math.isfinite(gap_seconds) or gap_seconds < 0:
        raise ValueError("gap_seconds must be finite and non-negative")
    if minimum_match_characters < 1:
        raise ValueError("minimum_match_characters must be positive")
    minimum = minimum_match_characters
    kept, dropped, alias = _dedup(messages)
    ordered = sorted(kept.values(), key=_order)
    union = _Union(kept)
    links: list[ThreadLink] = []
    edges: set[tuple[str, str]] = set()

    def link(child: str, parent: str, reason: LinkReason) -> None:
        if child == parent or (child, parent) in edges:
            return
        edges.add((child, parent))
        links.append(ThreadLink(child_id=child, parent_id=parent, reason=reason))
        if parent in union:
            union.union(child, parent)

    for message in ordered:
        for reference in (message.in_reply_to, *message.references):
            parent = alias.get(reference, reference)
            if parent in kept:
                link(message.message_id, parent, LinkReason.HEADER)

    normalized_own = {m.message_id: _normalize(m.own_text) for m in ordered}
    index: dict[str, list[str]] = {}
    for message in ordered:
        text = normalized_own[message.message_id]
        if len(text) >= minimum:
            index.setdefault(text[:minimum], []).append(message.message_id)

    matched: set[tuple[str, int]] = set()
    for message in ordered:
        for position, fragment in enumerate(message.fragments):
            if fragment.kind not in _QUOTE_KINDS:
                continue
            text = _normalize(fragment.text)
            if len(text) < minimum:
                continue
            anchor = fragment.timestamp or message.timestamp
            candidates = [
                c
                for c in _nearest(index.get(text[:minimum], []), anchor, kept)
                if c != message.message_id
                and _prefix_related(text, normalized_own[c], minimum)
            ]
            if not candidates:
                continue

            def rank(
                candidate: str,
                fragment: Fragment = fragment,
                message: EmailMessage = message,
            ) -> tuple[int, int, float, str]:
                other = kept[candidate]
                return (
                    0 if _sender_matches(other, fragment) else 1,
                    0 if other.subject_key == message.subject_key else 1,
                    other.timestamp,
                    other.message_id,
                )

            matched.add((message.message_id, position))
            link(message.message_id, min(candidates, key=rank), LinkReason.QUOTED)

    for message in ordered:
        body = _normalize(message.raw_body)
        position, limit = 0, len(body) - minimum
        while position <= limit:
            skip = 1
            bucket = index.get(body[position : position + minimum], [])
            for candidate in _nearest(bucket, message.timestamp, kept):
                other = kept[candidate]
                if candidate == message.message_id or _order(other) >= _order(message):
                    continue
                text = normalized_own[candidate]
                if body.startswith(text, position):
                    link(message.message_id, candidate, LinkReason.SUBSET)
                    skip = max(skip, len(text))
            position += skip

    buckets: dict[str, list[EmailMessage]] = {}
    for message in ordered:
        if message.subject_key and message.subject_key != NO_SUBJECT:
            buckets.setdefault(message.subject_key, []).append(message)
    for _, members in sorted(buckets.items()):
        latest: dict[str, EmailMessage] = {}
        people: dict[str, set[str]] = {}
        for message in members:
            for root in [
                r
                for r, a in latest.items()
                if message.timestamp - a.timestamp > gap_seconds
            ]:
                del latest[root]
            others = message.participants - {message.sender}
            touched = {union.find(message.message_id)}
            for root in sorted(latest):
                if root not in touched and others & people[root]:
                    link(
                        message.message_id, latest[root].message_id, LinkReason.SUBJECT
                    )
                    touched.add(root)
            root = union.find(message.message_id)
            group = people.setdefault(root, set())
            group.update(message.participants)
            for old in touched:
                if old != root and old in people:
                    group |= people.pop(old)
                latest.pop(old, None)
            latest[root] = message
            while len(latest) > _BUCKET_LIMIT:
                del latest[next(iter(latest))]

    reconstructed: dict[str, EmailMessage] = {}
    owner: dict[str, str] = {}
    if reconstruct:
        for message in ordered:
            for position, fragment in enumerate(message.fragments):
                if (
                    fragment.kind not in _QUOTE_KINDS
                    or not fragment.sender
                    or not fragment.text.strip()
                    or (message.message_id, position) in matched
                ):
                    continue
                text = _normalize(fragment.text)
                identity = (
                    "reconstructed:"
                    + _digest(
                        [
                            fragment.sender,
                            int(fragment.timestamp),
                            message.subject_key,
                            text,
                        ]
                    )[:24]
                )
                if identity not in reconstructed:
                    reconstructed[identity] = EmailMessage(
                        message_id=identity,
                        timestamp=fragment.timestamp or message.timestamp - 1,
                        sender=fragment.sender,
                        to=fragment.recipients,
                        subject=fragment.subject or message.subject,
                        subject_key=message.subject_key,
                        raw_body=fragment.text,
                        own_text=fragment.text,
                        source=message.source,
                    )
                    owner[identity] = message.message_id
                else:
                    union.union(owner[identity], message.message_id)
                link(message.message_id, identity, LinkReason.QUOTED)

    members_by_root: dict[str, list[EmailMessage]] = {}
    for message in ordered:
        members_by_root.setdefault(union.find(message.message_id), []).append(message)
    recovered_by_root: dict[str, list[EmailMessage]] = {}
    for identity, message in reconstructed.items():
        recovered_by_root.setdefault(union.find(owner[identity]), []).append(message)
    duplicates_by_root: dict[str, set[str]] = {}
    for dropped_id, original in dropped:
        root = union.find(alias.get(original, original))
        duplicates_by_root.setdefault(root, set()).add(dropped_id)
    links_by_root: dict[str, list[ThreadLink]] = {}
    for item in links:
        links_by_root.setdefault(union.find(item.child_id), []).append(item)
    threads = [
        EmailThread(
            thread_id="thread:" + _digest(sorted(m.message_id for m in members))[:24],
            messages=tuple(members),
            reconstructed=tuple(sorted(recovered_by_root.get(root, ()), key=_order)),
            duplicates=tuple(sorted(duplicates_by_root.get(root, ()))),
            links=tuple(links_by_root.get(root, ())),
        )
        for root, members in members_by_root.items()
    ]
    return tuple(sorted(threads, key=lambda t: (t.messages[0].timestamp, t.thread_id)))


def email_events(
    thread: EmailThread,
    *,
    scope: str,
    stream: str = "",
    url_for: Callable[[EmailMessage], str] | None = None,
    include_reconstructed: bool = True,
) -> tuple[KnowledgeEvent, ...]:
    """Adapt one thread into knowledge events; own words only, never quoted copies."""
    recovered = {m.message_id for m in thread.reconstructed}
    members = [
        *thread.messages,
        *(thread.reconstructed if include_reconstructed else ()),
    ]
    events: list[KnowledgeEvent] = []
    for message in sorted(members, key=_order):
        if not message.own_text.strip():
            continue
        lines = [f"Subject: {message.subject}"]
        if message.to:
            lines.append(f"To: {', '.join(message.to[:20])}")
        text = "\n".join(lines) + "\n\n" + message.own_text
        events.append(
            KnowledgeEvent(
                event_id=message.message_id,
                scope=scope,
                stream=stream or thread.thread_id,
                revision=hashlib.sha256(text.encode()).hexdigest()[:12],
                timestamp=message.timestamp,
                author=message.sender or "unknown",
                text=text,
                thread_id=thread.thread_id,
                url=url_for(message) if url_for else message.source,
                role="quoted" if message.message_id in recovered else "message",
            )
        )
    return tuple(events)


__all__ = [
    "EmailThread",
    "LinkReason",
    "ThreadLink",
    "email_events",
    "thread_emails",
]
