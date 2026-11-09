"""energyplus_toolkit.input (the input data model) must not depend on the tools: it will become its own package."""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).parent.parent / "energyplus_toolkit"
INPUT_FILES = sorted((PACKAGE / "input").rglob("*.py"))


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            modules.append(node.module)
    return modules


def test_input_files_found():
    assert INPUT_FILES


@pytest.mark.parametrize("path", INPUT_FILES, ids=lambda p: str(p.relative_to(PACKAGE)))
def test_input_only_imports_input(path):
    toolkit_imports = [m for m in _imported_modules(path) if m.split(".")[0] == "energyplus_toolkit"]
    assert all(m.startswith("energyplus_toolkit.input") for m in toolkit_imports), toolkit_imports
