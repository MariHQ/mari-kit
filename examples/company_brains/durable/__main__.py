"""Run a persistent company-brain lifecycle using synthetic source documents."""

from __future__ import annotations

import argparse
import json
import tempfile
from dataclasses import replace
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
from mari_kit.sync import plan_sync

from .engine import CompanyBrain
from .store import SQLiteBrainStore


def run(path: str | Path, *, generate=None) -> dict:
    scope = ScopeRef(tenant="durable-demo", space="company")
    source = "handbook"
    question = "What is the refund window?"
    policy = KnowledgeDocument(
        source_id=source,
        external_id="refunds",
        title="Refund policy",
        body="The refund window is 30 days.",
        revision="v1",
        acl=DocumentACL(
            visibility="restricted",
            principals=(Principal(kind="team", identifier="support"),),
        ),
    )
    public = KnowledgeDocument(
        source_id=source,
        external_id="onboarding",
        title="Onboarding",
        body="New employees attend orientation on Monday.",
        revision="v1",
        acl=DocumentACL(visibility="public"),
    )

    def apply(store, *, documents=(), tombstones=(), mode=SyncMode.INCREMENTAL):
        plan = plan_sync(
            store.state(scope, source),
            PollPage(
                upserts=tuple(documents),
                tombstones=tuple(tombstones),
                snapshot_complete=True,
            ),
            source_id=source,
            mode=mode,
        )
        store.apply_plan(scope, plan)

    with SQLiteBrainStore(path) as store:
        apply(store, documents=(policy, public), mode=SyncMode.FULL)
        store.set_groups(scope, "alice", ("support",))
        store.set_groups(scope, "bob", ("support",))
        brain = CompanyBrain(store, scope)
        first = brain.answer(question, user_id="alice", generate=generate)
        warm = brain.answer(question, user_id="alice", generate=generate)
    with SQLiteBrainStore(path) as store:
        brain = CompanyBrain(store, scope)
        restarted = brain.answer(question, user_id="alice", generate=generate)
        store.set_groups(scope, "alice", ())
        revoked = brain.answer(question, user_id="alice", generate=generate)
        retained = brain.answer(question, user_id="bob", generate=generate)
        revised = replace(
            policy,
            body="The refund window is 45 days.",
            revision="v2",
            content_digest="",
        )
        apply(store, documents=(revised,))
        edited = brain.answer(question, user_id="bob", generate=generate)
        private = replace(
            revised,
            acl=DocumentACL(
                visibility="restricted",
                principals=(Principal(kind="team", identifier="finance"),),
            ),
        )
        apply(store, documents=(private,))
        acl_revoked = brain.answer(question, user_id="bob", generate=generate)
        store.set_groups(scope, "carol", ("finance",))
        finance = brain.answer(question, user_id="carol", generate=generate)
        apply(
            store,
            tombstones=(Tombstone(source_id=source, external_id=policy.external_id),),
        )
        deleted = brain.answer(question, user_id="carol", generate=generate)
        projection = store.projection(scope)
        expected = {doc.document_id: doc.body for doc in store.documents(scope)}
        checks = {
            "initial_answer_grounded": first["disposition"] == "grounded",
            "warm_cache_reused": warm["cache_hit"],
            "cache_survives_restart": restarted["cache_hit"],
            "group_revocation_blocks_old_answer": revoked["disposition"]
            == "insufficient_evidence"
            and "30 days" not in revoked["answer"],
            "authorized_user_retains_access": retained["disposition"] == "grounded",
            "edit_replaces_old_answer": "45 days" in edited["answer"]
            and "30 days" not in edited["answer"],
            "same_revision_acl_change_blocks_cache": acl_revoked["disposition"]
            == "insufficient_evidence",
            "newly_authorized_user_can_answer": finance["disposition"] == "grounded",
            "deletion_blocks_cached_answer": deleted["disposition"]
            == "insufficient_evidence",
            "projection_matches_current_documents": projection == expected,
        }
        return {
            "passed": all(checks.values()),
            "checks": checks,
            "database": str(path),
            "source_generation": store.state(scope, source).generation,
            "remaining_document_ids": sorted(projection),
            "mode": "deterministic extractive fixture; durable SQLite storage",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        help="Persist the synthetic demo in this database (tenant durable-demo).",
    )
    args = parser.parse_args()
    if args.db is None:
        with tempfile.TemporaryDirectory(prefix="mari-company-brain-") as directory:
            result = run(Path(directory) / "brain.sqlite")
    else:
        args.db.parent.mkdir(parents=True, exist_ok=True)
        result = run(args.db)
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
