from __future__ import annotations

import ast
import tomllib
import unittest
from pathlib import Path


class ArchitectureTests(unittest.TestCase):
    @property
    def repository(self):
        return Path(__file__).parents[1]

    @property
    def package(self):
        return self.repository / "src" / "mari_components"

    def test_package_has_no_application_container(self):
        root = self.package
        self.assertFalse((root / "knowledge_base.py").exists())
        exported = (root / "__init__.py").read_text()
        self.assertNotIn("KnowledgeBase", exported)

    def test_core_has_no_host_framework_or_storage_imports(self):
        forbidden = {
            "fastapi",
            "strawberry",
            "psycopg",
            "sqlalchemy",
            "boto3",
            "sentence_transformers",
        }
        root = self.package
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

    def test_library_does_not_implement_an_agent_loop(self):
        root = self.package
        self.assertFalse((root / "agents" / "loop.py").exists())
        self.assertFalse((root / "agents" / "runtime.py").exists())
        for path in root.rglob("*.py"):
            self.assertNotIn("run_tool_loop", path.read_text())

    def test_library_does_not_discover_environment_or_start_processes(self):
        forbidden_imports = {"threading", "multiprocessing", "subprocess"}
        violations = []
        for path in self.package.rglob("*.py"):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name.split(".", 1)[0] for alias in node.names]
                    if forbidden_imports.intersection(names):
                        violations.append(str(path.relative_to(self.package)))
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.split(".", 1)[0] in forbidden_imports:
                        violations.append(str(path.relative_to(self.package)))
                elif isinstance(node, ast.Call) and isinstance(
                    node.func, ast.Attribute
                ):
                    owner = node.func.value
                    if (
                        isinstance(owner, ast.Name)
                        and owner.id == "os"
                        and node.func.attr in {"getenv"}
                    ):
                        violations.append(str(path.relative_to(self.package)))
                elif isinstance(node, ast.Attribute):
                    if (
                        isinstance(node.value, ast.Name)
                        and node.value.id == "os"
                        and node.attr == "environ"
                    ):
                        violations.append(str(path.relative_to(self.package)))
        self.assertEqual(violations, [])

    def test_repository_publishes_one_distribution(self):
        projects = tuple(self.repository.rglob("pyproject.toml"))
        self.assertEqual(projects, (self.repository / "pyproject.toml",))
        metadata = tomllib.loads(projects[0].read_text())
        self.assertEqual(metadata["project"]["name"], "mari-components")
        self.assertFalse((self.repository / "packages").exists())


if __name__ == "__main__":
    unittest.main()
