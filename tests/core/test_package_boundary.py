import ast
from pathlib import Path

import pytest

SOURCE = Path(__file__).parents[2] / "src" / "aidm"
CORE = ("kernel", "workflow")
FORBIDDEN = {
    "kernel": {"aidm.ui", "nicegui"},
    "workflow": {"aidm.ui", "nicegui"},
    # An engine ships its own panels, so it may import nicegui; `aidm.ui` stays closed to it.
    "plugins/story": {"aidm.plugins.dnd5e", "aidm.ui"},
    "plugins/dnd5e": {"aidm.plugins.story", "aidm.ui"},
}


def _source_files(package: str) -> tuple[Path, ...]:
    return tuple((SOURCE / package).rglob("*.py"))


def _package_of(path: Path) -> tuple[str, ...]:
    return path.relative_to(SOURCE.parent).with_suffix("").parts[:-1]


def _absolute(package: tuple[str, ...], node: ast.ImportFrom) -> str:
    """Resolve relative imports: the engines are siblings, so `from ..dnd5e` must be seen."""
    if node.level == 0:
        return node.module or ""
    parent = package[: len(package) - node.level + 1]
    return ".".join((*parent, node.module) if node.module else parent)


def _file_imports(path: Path) -> set[str]:
    imports: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(_absolute(_package_of(path), node))
    return imports


def _imports(package: str) -> set[str]:
    return {name for path in _source_files(package) for name in _file_imports(path)}


@pytest.mark.parametrize(("package", "forbidden"), FORBIDDEN.items())
def test_packages_import_only_in_the_allowed_direction(
    package: str,
    forbidden: set[str],
) -> None:
    imports = _imports(package)
    violations = {
        name
        for name in imports
        if any(name == root or name.startswith(f"{root}.") for root in forbidden)
    }
    assert not violations


def test_no_core_file_imports_an_engine_package() -> None:
    """Adding an engine is one line in `registry.ENGINE_MODULES`, the only place naming one."""
    naming = {
        path.name
        for package in CORE
        for path in _source_files(package)
        if any(name.startswith("aidm.plugins") for name in _file_imports(path))
    }
    assert naming == set()
