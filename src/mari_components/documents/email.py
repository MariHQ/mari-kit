"""RFC 822 email parsing with quoted-reply segmentation.

Standard library only. No filesystem or network access: the host reads the
bytes and passes them in. The parser separates the sender's own words from
quoted replies, forwarded blocks and signatures so that downstream threading
and extraction see each message once.
"""

from __future__ import annotations

import email
import email.policy
import hashlib
import quopri
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from email.message import Message
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from enum import StrEnum
from html.parser import HTMLParser


class FragmentKind(StrEnum):
    OWN = "own"
    QUOTED = "quoted"
    FORWARDED = "forwarded"
    SIGNATURE = "signature"


@dataclass(frozen=True, slots=True, kw_only=True)
class Fragment:
    """One contiguous region of a message body with a single provenance."""

    kind: FragmentKind
    text: str
    start: int
    end: int
    depth: int = 0
    sender: str = ""
    timestamp: float = 0.0
    subject: str = ""
    recipients: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0 <= self.start <= self.end:
            raise ValueError("fragment offsets must satisfy 0 <= start <= end")
        if self.depth < 0:
            raise ValueError("fragment depth cannot be negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class BulkSignal:
    """Header and shape evidence that a message is automated or bulk mail."""

    list_id: str = ""
    precedence: str = ""
    auto_submitted: str = ""
    noreply_sender: bool = False
    recipient_count: int = 0
    body_digest: str = ""

    @property
    def is_bulk(self) -> bool:
        return bool(
            self.list_id
            or self.precedence.lower() in {"bulk", "list", "junk"}
            or (self.auto_submitted and self.auto_submitted.lower() != "no")
            or self.noreply_sender
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class EmailMessage:
    """One parsed message. ``source`` is a caller-supplied locator, never derived."""

    message_id: str
    in_reply_to: str = ""
    references: tuple[str, ...] = ()
    timestamp: float = 0.0
    sender: str = ""
    sender_name: str = ""
    to: tuple[str, ...] = ()
    cc: tuple[str, ...] = ()
    bcc: tuple[str, ...] = ()
    subject: str = ""
    subject_key: str = ""
    raw_body: str = ""
    own_text: str = ""
    fragments: tuple[Fragment, ...] = ()
    bulk: BulkSignal = field(default_factory=BulkSignal)
    headers: Mapping[str, str] = field(default_factory=dict)
    attachments: tuple[str, ...] = ()
    source: str = ""

    def __post_init__(self) -> None:
        if not self.message_id.strip():
            raise ValueError("email message_id is required")

    @property
    def participants(self) -> frozenset[str]:
        """Every normalized address on the message, sender included."""
        return frozenset(a for a in (self.sender, *self.to, *self.cc, *self.bcc) if a)


_SUBJECT_PREFIX = re.compile(
    r"^(?:(?:re|fw|fwd|aw|tr|sv|wg)\s*(?:\[\d+\]|\(\d+\))?\s*:\s*|\[[^\]]*\]\s*)",
    re.IGNORECASE,
)
_MAILTO = re.compile(r"\[\s*mailto:\s*([^\]\s]+)\s*\]", re.IGNORECASE)
_ADDRESS = re.compile(
    r"[^\s<>\"',;:()\[\]]+@[^\s<>\"',;:()\[\]]+\.[^\s<>\"',;:()\[\]]+"
)
_ANGLE = re.compile(r"<([^<>]+)>")
_NOREPLY = re.compile(
    r"noreply|no-reply|donotreply|do-not-reply|mailer-daemon|bounces?|notifications?"
)

_QUOTE = re.compile(r"^\s*>")
_QUOTE_PREFIX = re.compile(r"^\s*(?:>\s?)+")
_HEADER = re.compile(
    r"^\s*(from|sent|to|cc|bcc|subject|date)\s*:[ \t]*(.*?)\s*$", re.IGNORECASE
)
# ``08/10/2001 11:06 AM``, ``07/11/2001 14:37`` or ``08/21/2001 01:48 PM CDT``.
_DATE_TOKEN = (
    r"\d{1,2}/\d{1,2}/\d{2,4}\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?(?:\s+[A-Z]{3,4})?"
)
_LOTUS_HEADER = re.compile(
    rf"^\s*(?:from\s*:[ \t]*)?([^\t:]{{1,80}}?)\s+on\s+({_DATE_TOKEN})\s*$",
    re.IGNORECASE,
)
_SENDER_DATE = re.compile(
    rf"^(.{{1,160}}?)\s+(?:on\s+)?({_DATE_TOKEN})\s*$", re.IGNORECASE
)
_NOTES_DATE = re.compile(rf"^\s*({_DATE_TOKEN})\s*$", re.IGNORECASE)
# One capitalized name token, optionally carrying a Notes org path: ``Gahn/HOU/EES@EES``.
_NOTES_NAME_TOKEN = r"[A-Z](?:\.|[\w'-]*)(?:/[\w'&.-]+)*(?:@[\w.-]+)?"
_NOTES_NAME = re.compile(rf"^{_NOTES_NAME_TOKEN}(?: {_NOTES_NAME_TOKEN}){{0,5}}$")
_OUTLOOK = re.compile(
    r"^\s*-{2,}\s*(?:original (?:message|appointment)|ursprüngliche nachricht"
    r"|message d'origine|mensaje original)\s*-{2,}\s*$",
    re.IGNORECASE,
)
_FORWARD = re.compile(
    r"^\s*-{2,}\s*forwarded (?:message|by .+? on .+?)\s*-{2,}\s*$"
    r"|^\s*begin forwarded message:?\s*$",
    re.IGNORECASE,
)
# Any dashed line naming a forwarder is a separator, closing dashes or not.
_FORWARD_ANY = re.compile(r"^\s*-{2,}.*\bforwarded by\b", re.IGNORECASE)
_FORWARD_BY = re.compile(
    rf"^\s*-{{2,}}\s*forwarded by\s+(.+?)\s+on\s+({_DATE_TOKEN})\s*(?:-{{2,}})?\s*$",
    re.IGNORECASE,
)
# The wrapped remainder of a marker: dashes alone, or a date/time, time or
# meridiem (with optional zone) followed by dashes.
_FORWARD_TAIL = re.compile(
    rf"^\s*(?:(?:{_DATE_TOKEN}|\d{{1,2}}:\d{{2}}(?::\d{{2}})?(?:\s*[AP]M)?(?:\s+[A-Z]{{3,4}})?"
    r"|[AP]M(?:\s+[A-Z]{3,4})?)\s+)?-{2,}\s*$",
    re.IGNORECASE,
)
_QP_LEFTOVER = re.compile(rb"=(?:\r?\n|09|20)")
_VERBS = r"(?:wrote|schrieb|a écrit|escribió)"
_ATTRIBUTION = re.compile(
    rf"^\s*.{{0,160}}?\b{_VERBS}\s*:\s*$"
    rf"|^\s*(?:am|le|el)\s.{{0,160}}\b{_VERBS}\b.{{0,80}}:\s*$",
    re.IGNORECASE,
)
_ATTRIBUTION_OPEN = re.compile(r"^\s*on\s.{0,120}$", re.IGNORECASE)
_SIGNATURE_MARKER = re.compile(
    r"^\s*(?:sent from (?:my )?[\w ]{1,30}\.?|get outlook for (?:ios|android))\s*$",
    re.IGNORECASE,
)
_PHONE = re.compile(r"(?:\+\d{1,3}[\s.-]?)?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]\d{3,4}\b")
_NAME_LINE = re.compile(r"^[A-Z][\w.'-]*(?: [A-Z][\w.'-]*){0,3},?$")
_SIGN_OFF = re.compile(
    r"^(?:thanks|thank you|thx|regards|best|best regards|kind regards|cheers"
    r"|sincerely|many thanks|talk soon)[,.!]?$",
    re.IGNORECASE,
)
_SENTENCE_PUNCTUATION = frozenset(".!?")
_MONTHS = {
    name: index
    for index, name in enumerate(
        (
            "jan", "feb", "mar", "apr", "may", "jun",
            "jul", "aug", "sep", "oct", "nov", "dec",
        ),
        start=1,
    )
}  # fmt: skip
_OFFSET = r"(?:\s*([+-]\d{4})\b)?"
_NUMERIC_DATE = re.compile(
    r"(\d{1,2})/(\d{1,2})/(\d{2,4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AP]M)?"
    + _OFFSET,
    re.IGNORECASE,
)
_WORDY_DATE = re.compile(
    r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AP]M)?"
    + _OFFSET,
    re.IGNORECASE,
)
_MERIDIEM = re.compile(r"\b[AP]M\b", re.IGNORECASE)


def subject_key(subject: str) -> str:
    """Normalize a subject for thread matching: strip reply/forward prefixes repeatedly."""
    key = " ".join(subject.split()).lower()
    while True:
        stripped = _SUBJECT_PREFIX.sub("", key, count=1).strip()
        if stripped == key:
            break
        key = stripped
    return key or "(no subject)"


def normalize_address(value: str) -> str:
    """Return the lowercase bare address from a display-name form, or ``""``."""
    text = " ".join(value.split())
    if not text:
        return ""
    mailto = _MAILTO.search(text)
    if mailto:
        return mailto.group(1).lower()
    _, address = parseaddr(text)
    if address and _ADDRESS.fullmatch(address):
        return address.lower()
    found = _ADDRESS.search(text)
    if found:
        return found.group(0).lower()
    angle = _ANGLE.search(text)
    token = angle.group(1) if angle else text
    token = " ".join(token.strip().strip("\"'").split()).lower()
    if not any(c.isalnum() for c in token):
        token = text.lower()
    return token if any(c.isalnum() for c in token) else ""


def _is_forward_marker(line: str) -> bool:
    return _FORWARD.match(line) is not None or _FORWARD_ANY.match(line) is not None


def _forward_tail(following: str | None) -> bool:
    """Whether the line after a ``Forwarded by`` marker is the marker's wrapped remainder."""
    return following is not None and _FORWARD_TAIL.match(following) is not None


def _notes_header(line: str, following: str | None) -> bool:
    """A bare Notes name line followed by a line holding only the date."""
    text = line.strip()
    return (
        following is not None
        and 0 < len(text) < 80
        and _NOTES_NAME.match(text) is not None
        and _NOTES_DATE.match(following) is not None
    )


def _starts_header_block(line: str, following: str | None = None) -> bool:
    header = _HEADER.match(line)
    if header is not None and header.group(1).lower() == "from":
        return True
    return _LOTUS_HEADER.match(line) is not None or _notes_header(line, following)


def _classify(line: str, following: str | None) -> tuple[str, bool]:
    """Return the category of ``line`` and whether ``following`` continues it."""
    if not line.strip():
        return "e", False
    if _QUOTE.match(line):
        return "q", False
    if _OUTLOOK.match(line) or _FORWARD.match(line) or _ATTRIBUTION.match(line):
        return "s", False
    if _FORWARD_ANY.match(line):
        return "s", _forward_tail(following)
    if (
        following is not None
        and _ATTRIBUTION_OPEN.match(line)
        and len(following) < 120
        and _ATTRIBUTION.match(following)
    ):
        return "s", True
    if _notes_header(line, following):
        return "h", True
    if _HEADER.match(line) or _LOTUS_HEADER.match(line):
        return "h", False
    if line.rstrip() == "--" or _SIGNATURE_MARKER.match(line):
        return "g", False
    return "t", False


def classify_lines(body: str) -> str:
    """One character per body line: t text, q quote, h header, s separator, g signature, e empty."""
    lines = body.split("\n")
    categories: list[str] = []
    index = 0
    while index < len(lines):
        following = lines[index + 1] if index + 1 < len(lines) else None
        category, wrapped = _classify(lines[index], following)
        categories.append(category)
        if wrapped:
            categories.append(category)
            index += 1
        index += 1
    return "".join(categories)


def _parse_timestamp(value: str) -> float:
    text = " ".join(value.split())
    if not text:
        return 0.0
    # The RFC 2822 parser silently drops an AM/PM token, so dates that carry one go
    # through the loose parser first.
    parsed = _parse_loose_datetime(text) if _MERIDIEM.search(text) else None
    if parsed is None:
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError, IndexError, OverflowError):
            parsed = None
    if parsed is None:
        parsed = _parse_loose_datetime(text)
    if parsed is None:
        return 0.0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    try:
        return parsed.timestamp()
    except (OverflowError, ValueError, OSError):
        return 0.0


def _parse_loose_datetime(text: str) -> datetime | None:
    numeric = _NUMERIC_DATE.search(text)
    if numeric:
        month, day, year, hour, minute, second, meridiem, offset = numeric.groups()
        first, second_field = int(month), int(day)
        if first > 12 and second_field <= 12:
            # Day-first mailboxes: ``13/01/2000`` can only be 13 January.
            first, second_field = second_field, first
        return _build_datetime(
            int(year), first, second_field, hour, minute, second, meridiem, offset
        )
    wordy = _WORDY_DATE.search(text)
    if wordy:
        name, day, year, hour, minute, second, meridiem, offset = wordy.groups()
        month = _MONTHS.get(name[:3].lower())
        if month is None:
            return None
        return _build_datetime(
            int(year), month, int(day), hour, minute, second, meridiem, offset
        )
    return None


def _build_datetime(
    year: int,
    month: int,
    day: int,
    hour: str,
    minute: str,
    second: str | None,
    meridiem: str | None,
    offset: str | None = None,
) -> datetime | None:
    if year < 100:
        year += 2000 if year < 70 else 1900
    hours = int(hour)
    if meridiem:
        hours %= 12
        if meridiem.upper() == "PM":
            hours += 12
    zone: timezone = UTC
    if offset:
        sign = -1 if offset[0] == "-" else 1
        delta = timedelta(hours=int(offset[1:3]), minutes=int(offset[3:5]))
        if delta < timedelta(hours=24):
            zone = timezone(sign * delta)
    try:
        return datetime(
            year, month, day, hours, int(minute), int(second or 0), tzinfo=zone
        )
    except ValueError:
        return None


def _split_addresses(value: str) -> tuple[str, ...]:
    """Split a recipient header on semicolons and commas without breaking ``Last, First`` names."""
    addresses: list[str] = []
    for piece in value.split(";"):
        if "@" not in piece:
            candidates = [piece] if piece.strip() else []
        else:
            pairs = [pair for pair in getaddresses([piece]) if pair[0] or pair[1]]
            if any("@" in address for _, address in pairs):
                # An unquoted ``Last, First <addr>`` yields a bare name token; drop it.
                pairs = [pair for pair in pairs if "@" in pair[1]]
            candidates = (
                [address or name for name, address in pairs]
                if pairs
                else [part for part in piece.split(",") if part.strip()]
            )
        for candidate in candidates:
            normalized = normalize_address(candidate)
            if normalized and normalized not in addresses:
                addresses.append(normalized)
    return tuple(addresses)


@dataclass(slots=True)
class _Meta:
    sender: str = ""
    timestamp: float = 0.0
    subject: str = ""
    recipients: tuple[str, ...] = ()


def _parse_header_block(lines: list[str]) -> _Meta:
    values: dict[str, str] = {}
    last = ""
    index = 0
    while index < len(lines):
        line = lines[index]
        following = lines[index + 1] if index + 1 < len(lines) else None
        header = _HEADER.match(line)
        if header is not None:
            last = header.group(1).lower()
            values[last] = header.group(2).strip()
        elif _notes_header(line, following):
            # Two-line Notes reply header: bare name, then the date on its own line.
            last = ""
            values["from"] = line.strip()
            values["date"] = lines[index + 1].strip()
            index += 1
        elif _LOTUS_HEADER.match(line):
            last = "from"
            values[last] = line.strip()
        elif last:
            values[last] = f"{values[last]} {line.strip()}".strip()
        index += 1
    meta = _Meta()
    sender = values.get("from", "")
    dated = _SENDER_DATE.match(sender)
    if dated:
        meta.sender = normalize_address(dated.group(1))
        meta.timestamp = _parse_timestamp(dated.group(2))
    elif sender:
        meta.sender = normalize_address(sender)
    for name in ("sent", "date"):
        if values.get(name):
            meta.timestamp = _parse_timestamp(values[name]) or meta.timestamp
            break
    meta.subject = " ".join(values.get("subject", "").split())
    recipients: list[str] = []
    for name in ("to", "cc"):
        for address in _split_addresses(values.get(name, "")):
            if address not in recipients:
                recipients.append(address)
    meta.recipients = tuple(recipients)
    return meta


def _fill_forward_meta(meta: _Meta, marker: list[str]) -> None:
    """Take sender and date from a ``Forwarded by NAME on DATE`` marker, one or two lines."""
    # Joined pairs go first: a wrapped meridiem or time would otherwise be dropped.
    joined = (
        f"{a.strip()} {b.strip()}" for a, b in zip(marker, marker[1:], strict=False)
    )
    for candidate in (*joined, *marker):
        found = _FORWARD_BY.match(candidate)
        if found is None:
            continue
        meta.sender = meta.sender or normalize_address(found.group(1))
        meta.timestamp = meta.timestamp or _parse_timestamp(found.group(2))
        return


@dataclass(slots=True)
class _Region:
    kind: FragmentKind
    depth: int
    start: int
    body: int
    end: int = 0
    meta: _Meta = field(default_factory=_Meta)
    quoted: bool = False
    continuation: bool = False


def _quote_depth(line: str) -> int:
    prefix = _QUOTE_PREFIX.match(line)
    return prefix.group(0).count(">") if prefix else 0


def _phone_line(line: str) -> bool:
    return _PHONE.search(line) is not None


def _short_plain_line(line: str) -> bool:
    text = line.strip()
    return 0 < len(text) < 40 and not any(c in _SENTENCE_PUNCTUATION for c in text)


def _looks_like_signature(block: list[str]) -> bool:
    if not block or len(block) > 6:
        return False
    stripped = [line.strip() for line in block]
    # A sentence anywhere in the block (other than on the phone line) means prose.
    if any(
        line and line[-1] in _SENTENCE_PUNCTUATION and not _phone_line(line)
        for line in stripped
    ):
        return False
    if not any(_NAME_LINE.match(line) or _SIGN_OFF.match(line) for line in stripped):
        return False
    if any(_phone_line(line) for line in block):
        return True
    if not (_NAME_LINE.match(stripped[0]) or _SIGN_OFF.match(stripped[0])):
        return False
    return sum(1 for line in block if _short_plain_line(line)) >= 2


def _detach_signature(
    regions: list[_Region], lines: list[str], categories: str
) -> None:
    """Split a trailing name/title/phone block off the last own region in place."""
    index = next(
        (
            i
            for i in range(len(regions) - 1, -1, -1)
            if regions[i].kind is FragmentKind.OWN
        ),
        None,
    )
    if index is None:
        return
    region = regions[index]
    last = region.end - 1
    while last >= region.body and categories[last] == "e":
        last -= 1
    first = last
    while first > region.body and categories[first - 1] != "e":
        first -= 1
    if first <= region.body:
        return
    if not any(categories[i] in "th" for i in range(region.body, first)):
        return
    if not _looks_like_signature(lines[first : last + 1]):
        return
    signature = _Region(
        kind=FragmentKind.SIGNATURE, depth=0, start=first, body=first, end=region.end
    )
    region.end = first
    regions.insert(index + 1, signature)


def _blank_run_inside_header(index: int, lines: list[str], categories: str) -> bool:
    """A blank line at ``index`` sits inside a header block when more pseudo-headers follow."""
    if categories[index] != "e":
        return False
    cursor = index
    while cursor < len(lines) and categories[cursor] == "e":
        cursor += 1
    if cursor >= len(lines) or categories[cursor] != "h":
        return False
    following = lines[cursor + 1] if cursor + 1 < len(lines) else None
    return not _starts_header_block(lines[cursor], following)


def _region_text(region: _Region, lines: list[str]) -> str:
    content = lines[region.body : region.end]
    if region.quoted:
        content = [_QUOTE_PREFIX.sub("", line) for line in content]
    elif region.kind is FragmentKind.SIGNATURE:
        content = [line for line in content if line.rstrip() != "--"]
    return "\n".join(line.rstrip() for line in content).strip()


def split_fragments(body: str) -> tuple[Fragment, ...]:
    """Segment a body into own, quoted, forwarded and signature fragments with offsets."""
    lines = body.split("\n")
    categories = classify_lines(body)
    count = len(lines)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line) + 1)
    regions: list[_Region] = []
    context = _Region(kind=FragmentKind.OWN, depth=0, start=0, body=0)

    def close(at: int) -> None:
        if context.start < at:
            context.end = at
            regions.append(context)

    index = 0
    while index < count:
        category = categories[index]
        line = lines[index]
        following = lines[index + 1] if index + 1 < count else None
        if category == "s" or (
            category == "h" and _starts_header_block(line, following)
        ):
            close(index)
            kind = (
                FragmentKind.FORWARDED
                if category == "s" and _is_forward_marker(line)
                else FragmentKind.QUOTED
            )
            cursor = index
            while cursor < count and categories[cursor] == "s":
                cursor += 1
            marker_end = cursor
            header_start = cursor
            while header_start < count and categories[header_start] == "e":
                header_start += 1
            header: list[str] = []
            if header_start < count and categories[header_start] == "h":
                cursor = header_start
                while cursor < count and (
                    categories[cursor] == "h"
                    or (
                        header
                        and categories[cursor] == "t"
                        and lines[cursor][:1] in " \t"
                    )
                    or (header and _blank_run_inside_header(cursor, lines, categories))
                ):
                    header.append(lines[cursor])
                    cursor += 1
            meta = _parse_header_block(header)
            if kind is FragmentKind.FORWARDED:
                _fill_forward_meta(meta, lines[index:marker_end])
            attribution = category == "s" and all(
                _ATTRIBUTION.match(lines[i]) or _ATTRIBUTION_OPEN.match(lines[i])
                for i in range(index, marker_end)
            )
            if attribution:
                for candidate in lines[index:marker_end]:
                    found = _ADDRESS.search(candidate)
                    if found:
                        meta.sender = found.group(0).lower()
                        break
            if (
                attribution
                and not header
                and header_start < count
                and categories[header_start] == "q"
            ):
                # An attribution above a ``>`` block owns exactly that quote run; the
                # writer's words resume below it (interleaved reply style).
                quote_depth = _quote_depth(lines[header_start])
                cursor = header_start
                while (
                    cursor < count
                    and categories[cursor] == "q"
                    and _quote_depth(lines[cursor]) == quote_depth
                ):
                    cursor += 1
                regions.append(
                    _Region(
                        kind=FragmentKind.QUOTED,
                        depth=context.depth + quote_depth,
                        start=index,
                        body=header_start,
                        end=cursor,
                        meta=meta,
                        quoted=True,
                    )
                )
                context = _Region(
                    kind=context.kind,
                    depth=context.depth,
                    start=cursor,
                    body=cursor,
                    meta=context.meta,
                    continuation=True,
                )
                index = cursor
                continue
            context = _Region(
                kind=kind, depth=context.depth + 1, start=index, body=cursor, meta=meta
            )
            index = cursor
            continue
        if category == "q":
            close(index)
            quote_depth = _quote_depth(line)
            cursor = index
            while (
                cursor < count
                and categories[cursor] == "q"
                and _quote_depth(lines[cursor]) == quote_depth
            ):
                cursor += 1
            regions.append(
                _Region(
                    kind=FragmentKind.QUOTED,
                    depth=context.depth + quote_depth,
                    start=index,
                    body=index,
                    end=cursor,
                    quoted=True,
                )
            )
            context = _Region(
                kind=context.kind,
                depth=context.depth,
                start=cursor,
                body=cursor,
                meta=context.meta,
                continuation=True,
            )
            index = cursor
            continue
        if category == "g" and context.kind is FragmentKind.OWN:
            close(index)
            cursor = index + 1
            while cursor < count and (
                categories[cursor] in "teg"
                or (
                    categories[cursor] == "h"
                    and not _starts_header_block(
                        lines[cursor],
                        lines[cursor + 1] if cursor + 1 < count else None,
                    )
                )
            ):
                cursor += 1
            regions.append(
                _Region(
                    kind=FragmentKind.SIGNATURE,
                    depth=0,
                    start=index,
                    body=index,
                    end=cursor,
                )
            )
            context = _Region(kind=FragmentKind.OWN, depth=0, start=cursor, body=cursor)
            index = cursor
            continue
        index += 1
    close(count)
    _detach_signature(regions, lines, categories)

    fragments: list[Fragment] = []
    for region in regions:
        text = _region_text(region, lines)
        meta = region.meta
        if not text and (
            region.continuation
            or not (meta.sender or meta.subject or meta.timestamp or meta.recipients)
        ):
            continue
        fragments.append(
            Fragment(
                kind=region.kind,
                text=text,
                start=offsets[region.start],
                end=min(offsets[region.end], len(body)),
                depth=region.depth,
                sender=meta.sender,
                timestamp=meta.timestamp,
                subject=meta.subject,
                recipients=meta.recipients,
            )
        )
    return tuple(fragments)


_HTML_BLOCKS = {
    "p", "div", "br", "li", "ul", "ol", "tr", "table", "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "pre", "hr", "section", "article", "header", "footer", "dd", "dt",
}  # fmt: skip
_HTML_SKIP = {"script", "style", "head", "title"}


class _TextExtractor(HTMLParser):
    """Collect visible text, breaking lines at block boundaries and prefixing quotes."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = [""]
        self.quote_depth = 0
        self.skip_depth = 0

    def _break(self) -> None:
        if self.lines[-1].strip():
            self.lines.append("")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        if tag in _HTML_SKIP:
            self.skip_depth += 1
        if tag in _HTML_BLOCKS:
            self._break()
        if tag == "blockquote":
            self.quote_depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in _HTML_BLOCKS:
            self._break()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in _HTML_SKIP and self.skip_depth:
            self.skip_depth -= 1
        if tag in _HTML_BLOCKS:
            self._break()
        if tag == "blockquote" and self.quote_depth:
            self.quote_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        for piece_index, piece in enumerate(data.split("\n")):
            if piece_index:
                self._break()
            text = " ".join(piece.split())
            if not text:
                continue
            if not self.lines[-1]:
                self.lines[-1] = ">" * self.quote_depth + (
                    " " if self.quote_depth else ""
                )
            elif not self.lines[-1].endswith(" "):
                self.lines[-1] += " "
            self.lines[-1] += text


def _html_to_text(source: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(source)
    extractor.close()
    lines = [line.rstrip() for line in extractor.lines]
    collapsed: list[str] = []
    for line in lines:
        if not line and collapsed and not collapsed[-1]:
            continue
        collapsed.append(line)
    return "\n".join(collapsed).strip()


def _looks_quoted_printable(payload: bytes) -> bool:
    """Undeclared quoted-printable: soft breaks, ``=09`` and ``=20`` dense enough to be encoding."""
    count = len(_QP_LEFTOVER.findall(payload))
    return count >= 3 and count * 2000 >= 3 * len(payload)


def _decode_part(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if isinstance(payload, str):
        return payload
    if not isinstance(payload, bytes):
        raw = part.get_payload()
        return raw if isinstance(raw, str) else ""
    if not _header(part, "Content-Transfer-Encoding") and _looks_quoted_printable(
        payload
    ):
        try:
            payload = quopri.decodestring(payload)
        except Exception:
            pass
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset)
    except (LookupError, UnicodeDecodeError):
        return payload.decode("utf-8", errors="replace")


def _header(message: Message, name: str) -> str:
    try:
        value = message.get(name)
    except Exception:
        return ""
    return " ".join(str(value).split()) if value is not None else ""


def _raw_header(message: Message, name: str) -> str:
    """The header as written, before the policy re-serializes it (Date drops AM/PM)."""
    wanted = name.lower()
    for key, value in message.raw_items():
        if key.lower() == wanted:
            return " ".join(str(value).split())
    return ""


def _header_list(message: Message, name: str) -> tuple[str, ...]:
    """Normalized addresses from the raw header text, so ``;`` lists survive intact."""
    wanted = name.lower()
    values = [
        " ".join(str(value).split())
        for key, value in message.raw_items()
        if key.lower() == wanted
    ]
    addresses: list[str] = []
    for value in values:
        for address in _split_addresses(value):
            if address not in addresses:
                addresses.append(address)
    return tuple(addresses)


def _collect_parts(
    part: Message,
    plain: list[str],
    html: list[str],
    attachments: list[str],
    *,
    top: bool = False,
) -> None:
    """Gather body text depth-first, never descending into attachments or attached messages."""
    filename = part.get_filename()
    disposition = (
        (part.get("Content-Disposition") or "").split(";", 1)[0].strip().lower()
    )
    content_type = part.get_content_type()
    if not top and (
        disposition == "attachment"
        or content_type == "message/rfc822"
        or (filename and part.get_content_maintype() != "text")
    ):
        if filename:
            attachments.append(" ".join(str(filename).split()))
        return
    if part.is_multipart():
        payload = part.get_payload()
        for sub in payload if isinstance(payload, list) else ():
            if isinstance(sub, Message):
                _collect_parts(sub, plain, html, attachments)
        return
    if content_type == "text/plain":
        plain.append(_decode_part(part))
    elif content_type == "text/html":
        html.append(_decode_part(part))


def _extract(message: Message, source: str) -> EmailMessage:
    headers: dict[str, str] = {}
    for name, value in message.items():
        headers.setdefault(name, str(value))
    plain: list[str] = []
    html: list[str] = []
    attachments: list[str] = []
    _collect_parts(message, plain, html, attachments, top=True)
    body = "\n".join(plain) if plain else _html_to_text("\n".join(html))
    raw_body = body.replace("\r\n", "\n").replace("\r", "\n")
    fragments = split_fragments(raw_body)
    own_text = "\n\n".join(
        f.text for f in fragments if f.kind is FragmentKind.OWN and f.text
    ).strip()

    from_value = _header(message, "From")
    sender = normalize_address(from_value)
    sender_name = " ".join(parseaddr(from_value)[0].split()).strip("\"'")
    timestamp = _parse_timestamp(
        _raw_header(message, "Date") or _header(message, "Date")
    )
    subject = _header(message, "Subject")
    key = subject_key(subject)
    to = _header_list(message, "To")
    cc = _header_list(message, "Cc")
    bcc = _header_list(message, "Bcc")

    message_id = _header(message, "Message-ID")
    if not message_id:
        seed = "\x1f".join((sender, repr(timestamp), key, " ".join(own_text.split())))
        message_id = "synthetic:" + hashlib.sha256(seed.encode()).hexdigest()[:24]
    local_part = sender.split("@", 1)[0]
    digest_source = " ".join(own_text.lower().split())
    bulk = BulkSignal(
        list_id=_header(message, "List-Id"),
        precedence=_header(message, "Precedence"),
        auto_submitted=_header(message, "Auto-Submitted"),
        noreply_sender=bool(local_part and _NOREPLY.search(local_part)),
        recipient_count=len(to) + len(cc) + len(bcc),
        body_digest=hashlib.sha256(digest_source.encode()).hexdigest()[:24],
    )
    return EmailMessage(
        message_id=message_id,
        in_reply_to=_header(message, "In-Reply-To"),
        references=tuple(_header(message, "References").split()),
        timestamp=timestamp,
        sender=sender,
        sender_name=sender_name,
        to=to,
        cc=cc,
        bcc=bcc,
        subject=subject,
        subject_key=key,
        raw_body=raw_body,
        own_text=own_text,
        fragments=fragments,
        bulk=bulk,
        headers=headers,
        attachments=tuple(attachments),
        source=source,
    )


def parse_email(raw: bytes | str, *, source: str = "") -> EmailMessage:
    """Parse one RFC 822 message. Missing Message-ID values are synthesized deterministically."""
    try:
        if isinstance(raw, bytes):
            message = email.message_from_bytes(raw, policy=email.policy.default)
        else:
            message = email.message_from_string(raw, policy=email.policy.default)
        return _extract(message, source)
    except Exception:
        if isinstance(raw, bytes):
            message = email.message_from_bytes(raw, policy=email.policy.compat32)
        else:
            message = email.message_from_string(raw, policy=email.policy.compat32)
        return _extract(message, source)


__all__ = [
    "BulkSignal",
    "EmailMessage",
    "Fragment",
    "FragmentKind",
    "classify_lines",
    "normalize_address",
    "parse_email",
    "split_fragments",
    "subject_key",
]
