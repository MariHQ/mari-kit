from __future__ import annotations

import ast
from pathlib import Path
import unittest


class ArchitectureTests(unittest.TestCase):
    def test_package_has_no_application_container(self):
        root = Path(__file__).parents[1] / "src" / "mari_components"
        self.assertFalse((root / "knowledge_base.py").exists())
        exported = (root / "__init__.py").read_text()
        self.assertNotIn("KnowledgeBase", exported)

    def test_core_has_no_host_framework_or_storage_imports(self):
        forbidden = {"fastapi", "strawberry", "psycopg", "sqlalchemy", "boto3", "sentence_transformers"}
        root = Path(__file__).parents[1] / "src" / "mari_components"
        found = []
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    if name.split(".", 1)[0] in forbidden:
                        found.append(f"{path.relative_to(root)}: {name}")
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
