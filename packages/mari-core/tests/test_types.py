from __future__ import annotations

import unittest

from mari_components import DocumentACL, KnowledgeDocument, PollRequest, Principal


class TypesTests(unittest.TestCase):
    def test_document_requires_stable_identity(self):
        with self.assertRaises(ValueError):
            KnowledgeDocument("", "Title", "Body")

    def test_acl_is_explicit_and_immutable(self):
        acl = DocumentACL("restricted", (Principal("group", "engineering"),))
        document = KnowledgeDocument("page:1", "One", "Body", acl=acl)
        self.assertEqual(document.acl.principals[0].identifier, "engineering")
        with self.assertRaises(AttributeError):
            document.title = "Changed"  # type: ignore[misc]

    def test_poll_limits_are_positive(self):
        with self.assertRaises(ValueError):
            PollRequest(page_size=0)


if __name__ == "__main__":
    unittest.main()
