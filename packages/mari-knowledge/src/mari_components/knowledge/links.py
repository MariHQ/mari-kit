"""Explicit-reference parsing and caller-scored semantic link selection."""

from __future__ import annotations

from dataclasses import dataclass
import posixpath
import re
from typing import Callable, Iterable, Mapping
from urllib.parse import unquote, urlparse


MARKDOWN_LINK = re.compile(r'\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)')
REFERENCE = re.compile(r"(?<![\w/&#])#(\d+)\b")
DEFAULT_SIMILARITY_THRESHOLD = 0.78
DEFAULT_SIMILARITY_LIMIT = 3


@dataclass(frozen=True, slots=True)
class LinkCandidate:
    source_id: str
    target_id: str
    kind: str
    score: float = 1.0


def _resolve(base_path: str, target: str) -> str | None:
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or target.startswith(("#", "mailto:")):
        return None
    clean = unquote(parsed.path).strip()
    if not clean:
        return None
    resolved = (posixpath.normpath(clean.lstrip("/")) if clean.startswith("/")
                else posixpath.normpath(posixpath.join(posixpath.dirname(base_path), clean)))
    return None if resolved == ".." or resolved.startswith("../") else resolved


def extract_explicit_links(source_id: str, source_path: str, body: str, path_to_id: Mapping[str, str]) -> tuple[LinkCandidate, ...]:
    output: set[LinkCandidate] = set()
    for match in REFERENCE.finditer(body):
        target = path_to_id.get(match.group(1))
        if target and target != source_id:
            output.add(LinkCandidate(source_id, target, "references"))
    for raw in MARKDOWN_LINK.findall(body):
        resolved = _resolve(source_path, raw)
        target = (path_to_id.get(resolved or "")
                  or path_to_id.get((resolved or "") + ".md")
                  or path_to_id.get(posixpath.join(resolved or "", "README.md")))
        if target and target != source_id:
            output.add(LinkCandidate(source_id, target, "links_to"))
    return tuple(sorted(output, key=lambda link: (link.kind, link.target_id)))


def derive_links(source_id: str, candidate_ids: Iterable[str], *, score: Callable[[str, str], float], threshold: float = DEFAULT_SIMILARITY_THRESHOLD, limit: int = DEFAULT_SIMILARITY_LIMIT) -> tuple[LinkCandidate, ...]:
    if not 0 <= threshold <= 1 or limit < 1:
        raise ValueError("threshold must be 0..1 and limit positive")
    ranked = sorted(((candidate, float(score(source_id, candidate))) for candidate in candidate_ids if candidate != source_id), key=lambda pair: (-pair[1], pair[0]))
    return tuple(LinkCandidate(source_id, target, "similar", value) for target, value in ranked if value >= threshold)[:limit]
