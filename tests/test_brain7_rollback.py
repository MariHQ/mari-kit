"""Preserve SQLite's original failure after an automatic transaction rollback."""

import sqlite3

import pytest

from examples.company_brains.durable.store import SQLiteBrainStore
from mari_kit import ScopeRef


def test_membership_auto_rollback_preserves_error_and_connection(tmp_path):
    scope = ScopeRef(tenant="recovery", space="brain")
    with SQLiteBrainStore(tmp_path / "brain.sqlite3") as store:
        store.set_groups(scope, "alice", ["support"])
        before = store.access_token(scope, "alice")
        store._connection.execute(
            "CREATE TRIGGER reject_group BEFORE INSERT ON groups "
            "BEGIN SELECT RAISE(ROLLBACK, 'membership update rejected'); END"
        )
        with pytest.raises(sqlite3.IntegrityError, match="membership update rejected"):
            store.set_groups(scope, "alice", ["finance"])

        assert store.groups(scope, "alice") == frozenset({"support"})
        assert store.access_token(scope, "alice") == before
        assert not store._connection.in_transaction
        store._connection.execute("DROP TRIGGER reject_group")
        store.set_groups(scope, "alice", ["finance"])
        assert store.groups(scope, "alice") == frozenset({"finance"})
        assert store.access_token(scope, "alice").membership_epoch == (
            before.membership_epoch + 1
        )

    with SQLiteBrainStore(tmp_path / "brain.sqlite3") as reopened:
        assert reopened.groups(scope, "alice") == frozenset({"finance"})
        assert reopened.access_token(scope, "alice").membership_epoch == (
            before.membership_epoch + 1
        )
