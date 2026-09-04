"""Deterministic in-memory knowledge bundles and import planning."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from mari_components.json import canonical_json_bytes


def _canonical(value: Any) -> bytes:
    return canonical_json_bytes(value)


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeBundle:
    files: Mapping[str, bytes]

    def __post_init__(self) -> None:
        object.__setattr__(self, "files", MappingProxyType(dict(self.files)))


@dataclass(frozen=True, slots=True, kw_only=True)
class BundleVerification:
    valid: bool
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class BundleImportPlan:
    add_content_ids: tuple[str, ...]
    existing_content_ids: tuple[str, ...]


def _jsonl(values: Iterable[Any]) -> bytes:
    rows = sorted(_canonical(value) for value in values)
    return b"\n".join(rows) + (b"\n" if rows else b"")


def export_bundle(
    *,
    records: Iterable[Any],
    provenance: Iterable[Any] = (),
    tombstones: Iterable[Any] = (),
    scopes: Iterable[str] = (),
) -> KnowledgeBundle:
    data = {
        "records.jsonl": _jsonl(records),
        "provenance.jsonl": _jsonl(provenance),
        "tombstones.jsonl": _jsonl(tombstones),
    }
    checksums = {
        name: hashlib.sha256(content).hexdigest() for name, content in data.items()
    }
    manifest = {
        "format": "mari-knowledge-bundle",
        "version": 1,
        "scopes": sorted(set(scopes)),
        "checksums": checksums,
    }
    data["manifest.json"] = _canonical(manifest) + b"\n"
    data["checksums.sha256"] = "".join(
        f"{digest}  {name}\n" for name, digest in sorted(checksums.items())
    ).encode()
    return KnowledgeBundle(files=data)


def verify_bundle(bundle: KnowledgeBundle) -> BundleVerification:
    errors: list[str] = []
    try:
        manifest = json.loads(bundle.files["manifest.json"])
    except (KeyError, json.JSONDecodeError, UnicodeDecodeError):
        return BundleVerification(valid=False, errors=("invalid_manifest",))
    if (
        manifest.get("format") != "mari-knowledge-bundle"
        or manifest.get("version") != 1
    ):
        errors.append("unsupported_format")
    for name, expected in manifest.get("checksums", {}).items():
        content = bundle.files.get(name)
        if content is None or hashlib.sha256(content).hexdigest() != expected:
            errors.append(f"checksum:{name}")
    return BundleVerification(valid=not errors, errors=tuple(errors))


def plan_bundle_import(
    bundle: KnowledgeBundle, *, existing_ids: Iterable[str] = ()
) -> BundleImportPlan:
    report = verify_bundle(bundle)
    if not report.valid:
        raise ValueError(f"bundle verification failed: {report.errors}")
    existing = set(existing_ids)
    rows = [line for line in bundle.files["records.jsonl"].splitlines() if line]
    ids = tuple(hashlib.sha256(line).hexdigest() for line in rows)
    return BundleImportPlan(
        add_content_ids=tuple(value for value in ids if value not in existing),
        existing_content_ids=tuple(value for value in ids if value in existing),
    )
