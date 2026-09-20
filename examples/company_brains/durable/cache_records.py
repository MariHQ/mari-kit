"""Validate the host-owned persisted answer record before attempting reuse."""

import hashlib
from collections.abc import Mapping

from mari_kit.json import canonical_json_bytes


def seal_cache_record(payload: Mapping[str, object]) -> dict[str, object]:
    """Add an unkeyed checksum for accidental corruption, not authentication."""
    record = {key: value for key, value in payload.items() if key != "checksum"}
    record["checksum"] = hashlib.sha256(canonical_json_bytes(record)).hexdigest()
    return record


def cache_record_matches_request(
    payload: Mapping[str, object],
    *,
    schema: str,
    question: str,
    user_id: str,
    scope_key: tuple[str, str],
) -> bool:
    """Reject malformed or misbound records; source freshness is checked later.

    This checks representation and request identity, not the semantic truth of
    cached prose. The database and cache-writing application remain trusted.
    """
    if (
        payload.get("schema") != schema
        or payload.get("question") != question
        or payload.get("user_id") != user_id
        or payload.get("scope_key") != list(scope_key)
        or not isinstance(payload.get("answer"), str)
        or not payload["answer"].strip()
    ):
        return False
    try:
        if payload.get("checksum") != seal_cache_record(payload)["checksum"]:
            return False
    except (TypeError, ValueError, RecursionError):
        return False
    disposition = payload.get("disposition")
    if disposition not in ("grounded", "insufficient_evidence"):
        return False
    # Schema v3 persists one compact SHA-256 digest of the whole authorized set
    # rather than the full per-document fingerprint list.  Missing, empty, or
    # non-string material is rejected here; the live digest is compared later.
    digest = payload.get("authorized_fingerprint")
    if not isinstance(digest, str) or not digest.strip():
        return False
    evidence = payload.get("evidence")
    dependencies = payload.get("dependencies")
    if not isinstance(evidence, list) or not isinstance(dependencies, list):
        return False
    if disposition == "insufficient_evidence" and not evidence:
        return not dependencies
    if not evidence or not dependencies:
        return False
    for record in evidence:
        if not isinstance(record, Mapping) or not all(
            isinstance(record.get(key), str) and record[key].strip()
            for key in ("document_id", "revision", "quote")
        ):
            return False
        if "section_id" in record and not isinstance(record["section_id"], str):
            return False
        start, end = record.get("start"), record.get("end")
        if (start is None) != (end is None):
            return False
        if start is not None and (
            type(start) is not int or type(end) is not int or start < 0 or end <= start
        ):
            return False
    for record in dependencies:
        if not isinstance(record, Mapping) or not all(
            isinstance(record.get(key), str) and record[key].strip()
            for key in ("document_id", "revision", "content_digest")
        ):
            return False
    return {(row["document_id"], row["revision"]) for row in evidence} == {
        (row["document_id"], row["revision"]) for row in dependencies
    }
