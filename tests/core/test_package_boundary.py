import ast
from pathlib import Path

import pytest

SOURCE = Path(__file__).parents[2] / "src"
FORBIDDEN = {
    "aidm": {"aidm_ui", "nicegui"},
    "aidm_story": {"aidm_5e", "aidm_ui", "nicegui"},
    "aidm_5e": {"aidm_story", "aidm_ui", "nicegui"},
}


def _imported_roots(package: str) -> set[str]:
    roots: set[str] = set()
    for path in (SOURCE / package).rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots.add(node.module.split(".", 1)[0])
    return roots


@pytest.mark.parametrize(("package", "forbidden"), FORBIDDEN.items())
def test_packages_import_only_in_the_allowed_direction(
    package: str,
    forbidden: set[str],
) -> None:
    assert _imported_roots(package).isdisjoint(forbidden)
