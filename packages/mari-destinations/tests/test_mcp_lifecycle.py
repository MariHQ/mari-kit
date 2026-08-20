from __future__ import annotations

import unittest

from mari_components.destinations.mcp_lifecycle import McpPorts, create_server, delete_server, test_server


def ports(**overrides):
    values = dict(
        name_exists=lambda _project, _name: False,
        insert=lambda *_args: None,
        update=lambda *_args: True,
        delete=lambda _project, _server: "Server",
        inspect=lambda _project, _server: {"capabilities": ("search", "chat")},
        capability_counts=lambda _project, _caps: {"search": 3, "chat": 1},
        mark_connected=lambda *_args: None,
        audit=lambda *_args: None,
        issue_token=lambda: "mari_mcp_secret",
    )
    values.update(overrides)
    return McpPorts(**values)


class McpApplicationTests(unittest.TestCase):
    def test_create_validates_then_persists_hash_only(self) -> None:
        inserted = []
        token = create_server(
            7, "Support KB", "workspace", ["search", "facts", "search"],
            base_url="https://mari.example", ports=ports(insert=lambda *args: inserted.append(args)),
        )
        self.assertEqual(token, "mari_mcp_secret")
        project, spec, url, token_hash, tools = inserted[0]
        self.assertEqual((project, spec.capabilities, url, tools),
                         (7, ("search", "facts"), "https://mari.example/mcp/support-kb", 2))
        self.assertNotEqual(token_hash, token)

    def test_duplicate_and_empty_capabilities_fail_before_insert(self) -> None:
        inserted = []
        with self.assertRaisesRegex(ValueError, "already exists"):
            create_server(7, "Same", "workspace", ["search"], base_url="https://mari",
                          ports=ports(name_exists=lambda *_args: True,
                                      insert=lambda *args: inserted.append(args)))
        with self.assertRaisesRegex(ValueError, "at least one"):
            create_server(7, "New", "workspace", ["unknown"], base_url="https://mari",
                          ports=ports(insert=lambda *args: inserted.append(args)))
        self.assertEqual(inserted, [])

    def test_test_and_delete_report_missing_servers_honestly(self) -> None:
        missing = ports(inspect=lambda *_args: None, delete=lambda *_args: None)
        self.assertEqual(test_server(7, 1, ports=missing), {"ok": False, "error": "not found"})
        self.assertFalse(delete_server(7, 1, ports=missing))


if __name__ == "__main__":
    unittest.main()
