"""Streaming knowledge-answer use case over product-neutral ports."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ChatContext:
    session_id: int
    sources: Sequence[Mapping[str, Any]]
    messages: Sequence[Mapping[str, str]]
    approved_answer: str = ""


@dataclass(frozen=True, slots=True)
class ChatEvent:
    kind: str
    payload: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ChatPorts:
    prepare: Callable[[int | None, str], ChatContext]
    generate: Callable[[Sequence[Mapping[str, str]]], Iterable[str]]
    persist: Callable[[int, str, Sequence[Mapping[str, Any]]], None]
    record_usage: Callable[[], None]


def stream_answer(session_id: int | None, message: str, *, ports: ChatPorts) -> Iterator[ChatEvent]:
    clean = (message or "").strip()[:8000]
    if not clean:
        raise ValueError("A message is required.")
    context = ports.prepare(session_id, clean)
    yield ChatEvent("meta", {
        "session_id": context.session_id,
        "sources": list(context.sources),
        "approved": bool(context.approved_answer),
    })
    parts: list[str] = []
    if context.approved_answer:
        parts.append(context.approved_answer)
        yield ChatEvent("token", {"token": context.approved_answer})
    else:
        for token in ports.generate(context.messages):
            text = str(token)
            parts.append(text)
            yield ChatEvent("token", {"token": text})
    if not parts:
        warning = "The configured language model is unavailable. Check model settings and try again."
        parts.append(warning)
        yield ChatEvent("warning", {"message": warning})
        yield ChatEvent("token", {"token": warning})
    ports.persist(context.session_id, "".join(parts), context.sources)
    ports.record_usage()
    yield ChatEvent("done", {"session_id": context.session_id})
