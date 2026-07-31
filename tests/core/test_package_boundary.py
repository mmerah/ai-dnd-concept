import ast
from pathlib import Path

CORE_SOURCE = Path(__file__).parents[2] / "src" / "aidm"
FORBIDDEN_ROOTS = {"aidm_5e", "aidm_story", "aidm_ui", "nicegui"}


def test_core_imports_no_rules_package_or_ui_framework() -> None:
    imported: set[str] = set()
    for path in CORE_SOURCE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".", 1)[0])

    assert imported.isdisjoint(FORBIDDEN_ROOTS)
