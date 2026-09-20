"""Subprocess harness that exercises crash durability of ``SQLiteBrainStore``.

Each invocation opens the durable store, performs exactly one operation, and
exits.  ``--stage`` installs a failpoint that calls ``os._exit(0)`` the moment
the store reports the named transaction stage, which simulates process death
without running any cleanup, ``finally`` block, or context-manager ``__exit__``.

Run as a module from the repository root so ``examples`` is importable::

    python -m examples.company_brains.durable.crash_worker --db /tmp/brain.db seed

The shared document fixtures live here so crash tests can compute an
independent expected snapshot with Mari Kit's pure planner while the child
process only mutates SQLite.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from mari_kit import (
    DocumentACL,
    KnowledgeDocument,
    PollPage,
    Principal,
    ScopeRef,
    SyncMode,
    Tombstone,
)
from mari_kit.json import to_json_value
from mari_kit.sync import plan_sync

SOURCE_ID = "handbook"
DEFAULT_SCOPE = ScopeRef(tenant="acme", space="brain")
STAGES = ("after_documents", "after_projection", "before_commit", "after_commit")


def document(
    external_id: str,
    revision: str,
    body: str,
    *,
    title: str | None = None,
    visibility: str = "connector_scope",
    principals: tuple[Principal, ...] = (),
    metadata: dict[str, object] | None = None,
    updated_at: str = "",
) -> KnowledgeDocument:
    """Build one provider revision with stable identity for every process."""

    return KnowledgeDocument(
        source_id=SOURCE_ID,
        external_id=external_id,
        title=title or f"Handbook {external_id}",
        body=body,
        revision=revision,
        updated_at=updated_at,
        acl=DocumentACL(visibility=visibility, principals=principals),
        metadata=metadata or {},
    )


def seed_documents() -> tuple[KnowledgeDocument, ...]:
    """Committed baseline: three connector-visible policy documents."""

    return (
        document("policy/leave", "r1", "Leave is twenty days."),
        document("policy/travel", "r1", "Travel requires approval."),
        document("policy/refunds", "r1", "Refunds within thirty days."),
    )


def seed_page() -> PollPage:
    return PollPage(
        upserts=seed_documents(),
        next_cursor="seed:1",
        snapshot_complete=True,
    )


def incremental_page() -> PollPage:
    """A single terminal incremental page: revise, add, and tombstone."""

    return PollPage(
        upserts=(
            document("policy/leave", "r2", "Leave is twenty-five days."),
            document(
                "policy/security",
                "r1",
                "Rotate secrets every ninety days.",
                visibility="restricted",
                principals=(Principal(kind="group", identifier="security"),),
                metadata={"owner": "security", "revision_note": "new policy"},
            ),
        ),
        tombstones=(Tombstone(source_id=SOURCE_ID, external_id="policy/travel"),),
        next_cursor="inc:1",
        snapshot_complete=True,
    )


def competing_page(tag: str) -> PollPage:
    """A distinct incremental change for each competing writer."""

    return PollPage(
        upserts=(document(f"policy/{tag}", "r1", f"Writer {tag} owns this policy."),),
        next_cursor=f"inc:{tag}",
        snapshot_complete=True,
    )


def full_snapshot_pages() -> tuple[PollPage, ...]:
    """Three-page authoritative snapshot: two docs, one doc, one terminal doc."""

    docs = (
        document("policy/leave", "r1", "Leave is twenty days."),
        document("policy/travel", "r1", "Travel requires approval."),
        document("policy/refunds", "r1", "Refunds within thirty days."),
        document("policy/security", "r1", "Rotate secrets every ninety days."),
    )
    return (
        PollPage(upserts=docs[:2], next_checkpoint="page:2", snapshot_complete=False),
        PollPage(upserts=docs[2:3], next_checkpoint="page:3", snapshot_complete=False),
        PollPage(upserts=docs[3:], next_cursor="full:done", snapshot_complete=True),
    )


def _store_class():
    from examples.company_brains.durable.store import SQLiteBrainStore

    return SQLiteBrainStore


def _planned(store, scope: ScopeRef, page: PollPage, mode: SyncMode):
    state = store.state(scope, SOURCE_ID)
    return plan_sync(state, page, source_id=SOURCE_ID, mode=mode)


def _crash_hook(stage: str | None, marker: Path | None):
    def hook(name: str) -> None:
        if stage is not None and name == stage:
            if marker is not None:
                marker.write_text(name, encoding="utf-8")
            os._exit(0)

    return hook


def _await_barrier(path: Path, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(0.01)
    raise SystemExit(f"barrier timeout waiting for {path}")


def _dump(store, scope: ScopeRef) -> None:
    documents = store.documents(scope)
    payload = {
        "state": store.state(scope, SOURCE_ID),
        "documents": [
            {
                "document_id": item.document_id,
                "external_id": item.external_id,
                "revision": item.revision,
                "body": item.body,
                "visibility": item.acl.visibility,
                "metadata": item.metadata,
            }
            for item in documents
        ],
        "projection": store.projection(scope),
    }
    print(json.dumps(to_json_value(payload), sort_keys=True))


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="crash_worker")
    parser.add_argument("--db", required=True)
    parser.add_argument("--tenant", default=DEFAULT_SCOPE.tenant)
    parser.add_argument("--space", default=DEFAULT_SCOPE.space)
    parser.add_argument(
        "--mode",
        required=True,
        choices=(
            "seed",
            "incremental-crash",
            "incremental-apply",
            "full-page",
            "read",
            "compete",
        ),
    )
    parser.add_argument("--stage", choices=STAGES)
    parser.add_argument("--marker")
    parser.add_argument("--page", type=int, default=0)
    parser.add_argument("--instance", default="0")
    parser.add_argument("--barrier")
    parser.add_argument("--barrier-timeout", type=float, default=30.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    scope = ScopeRef(tenant=args.tenant, space=args.space)
    store_cls = _store_class()
    marker = Path(args.marker) if args.marker else None
    store = store_cls(args.db)
    try:
        if args.mode == "seed":
            plan = _planned(store, scope, seed_page(), SyncMode.FULL)
            store.apply_plan(scope, plan)
        elif args.mode in {"incremental-crash", "incremental-apply"}:
            plan = _planned(store, scope, incremental_page(), SyncMode.INCREMENTAL)
            hook = None
            if args.mode == "incremental-crash":
                hook = _crash_hook(args.stage, marker)
            store.apply_plan(scope, plan, failpoint=hook)
        elif args.mode == "full-page":
            page = full_snapshot_pages()[args.page]
            plan = _planned(store, scope, page, SyncMode.FULL)
            store.apply_plan(scope, plan, failpoint=_crash_hook(args.stage, marker))
        elif args.mode == "read":
            _dump(store, scope)
        elif args.mode == "compete":
            plan = _planned(
                store, scope, competing_page(args.instance), SyncMode.INCREMENTAL
            )
            if not args.barrier:
                raise SystemExit("--barrier is required for compete mode")
            barrier = Path(args.barrier)
            barrier.mkdir(parents=True, exist_ok=True)
            (barrier / f"{args.instance}.gen").write_text(
                str(store.state(scope, SOURCE_ID).generation), encoding="utf-8"
            )
            sibling = "1" if args.instance == "0" else "0"
            _await_barrier(barrier / f"{sibling}.gen", args.barrier_timeout)
            store.apply_plan(scope, plan)
        else:  # pragma: no cover - argparse guarantees the choices above
            raise SystemExit(f"unsupported mode {args.mode!r}")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
