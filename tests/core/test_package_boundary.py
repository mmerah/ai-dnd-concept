import ast
from pathlib import Path

import pytest

SOURCE = Path(__file__).parents[2] / "src" / "aidm"
ENGINES = ("aidm.engines.loner3e",)
# The composition root builds the engine; the save payload is a closed union over engine states.
ROOTS = {"engines/registry.py", "state/model.py"}
# Flow: state <- kernel <- content <- kits <- engines <- turn <- app <- harness <- ui.
LAYERS = ("state", "kernel", "content", "kits", "engines", "turn", "app", "harness")
# The one inversion: `state.model` names the engine states its payload union is over, and those
# modules import nothing above `state.entities`.
ALLOWED = {"state": {"aidm.engines.loner3e.state"}}
# `ui` sits above them all, imports downwards, and additionally stays engine-agnostic.
TOPS = {"ui": {"aidm.engines"}}
# A framework belongs to the layers that own it and to nothing below them.
CONFINED = {
    "nicegui": ("ui",),
    "pydantic_ai": ("turn", "app", "ui", "harness"),
    "aidm.config": ("turn", "app", "ui", "harness"),
}


def _forbidden(package: str) -> set[str]:
    """What a package may not name: the layers downstream of it, its sibling top, its frameworks."""
    later = LAYERS[LAYERS.index(package) + 1 :] if package in LAYERS else ()
    siblings = (top for top in TOPS if top != package)
    downstream = {f"aidm.{name}" for name in (*later, *siblings)}
    confined = {name for name, owners in CONFINED.items() if package not in owners}
    return downstream | confined | TOPS.get(package, set())


FORBIDDEN = {package: _forbidden(package) for package in (*LAYERS, *TOPS)}


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
    allowed = ALLOWED.get(package, set())
    imports = {
        name
        for name in _imports(package)
        if not any(name == one or name.startswith(f"{one}.") for one in allowed)
    }
    violations = {
        name
        for name in imports
        if any(name == root or name.startswith(f"{root}.") for root in forbidden)
    }
    assert not violations


def test_no_module_names_a_concrete_engine() -> None:
    naming = {
        str(path.relative_to(SOURCE))
        for path in SOURCE.rglob("*.py")
        for name in _file_imports(path)
        if name.startswith(ENGINES)
        if not name.startswith(f"aidm.engines.{path.parts[-2]}")
    }
    assert naming == ROOTS
