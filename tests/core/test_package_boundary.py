import ast
from pathlib import Path

import pytest

SOURCE = Path(__file__).parents[2] / "src" / "aidm"
ENGINES = ("aidm.engines.loner3e", "aidm.engines.twentyfourxx")
# Dependencies flow state <- content <- engines <- turn <- app <- ui; config is a shared leaf.
FORBIDDEN = {
    "state": {"aidm.content", "aidm.engines", "aidm.turn", "aidm.app", "aidm.ui", "nicegui"},
    "content": {"aidm.engines", "aidm.turn", "aidm.app", "aidm.ui", "nicegui"},
    "engines": {"aidm.turn", "aidm.app", "aidm.ui"},
    "turn": {"aidm.app", "aidm.ui", "nicegui"},
    "app": {"aidm.ui", "nicegui"},
    "ui": {"aidm.engines"},
    # Each engine's mechanics stay pure Python; only its engine.py plugs into the model.
    "engines/loner3e/rules.py": {"pydantic_ai"},
    "engines/twentyfourxx/rules.py": {"pydantic_ai"},
}


def _source_files(package: str) -> tuple[Path, ...]:
    target = SOURCE / package
    files = (target,) if target.is_file() else tuple(target.rglob("*.py"))
    assert files, f"no python files under src/aidm/{package}: renamed without updating the tables?"
    return files


def _package_of(path: Path) -> tuple[str, ...]:
    return path.relative_to(SOURCE.parent).with_suffix("").parts[:-1]


def _absolute(package: tuple[str, ...], node: ast.ImportFrom) -> str:
    """Resolve relative imports: engines are siblings, so a `from ..sibling` must be seen."""
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
            base = _absolute(_package_of(path), node)
            imports.add(base)
            # `from package import module` stores the module in aliases, not `node.module`.
            imports.update(f"{base}.{alias.name}" for alias in node.names)
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


def test_only_the_loader_names_a_concrete_engine() -> None:
    naming = {
        str(path.relative_to(SOURCE))
        for path in SOURCE.rglob("*.py")
        for name in _file_imports(path)
        if name.startswith(ENGINES)
        if not name.startswith(f"aidm.engines.{path.parts[-2]}")
    }
    assert naming == {"app/launch.py"}
