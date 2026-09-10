import ast
from pathlib import Path

import pytest

SOURCE = Path(__file__).parents[2] / "src" / "aidm"
ENGINES = (
    "aidm.engines.loner3e",
    "aidm.engines.tunnelgoons",
    "aidm.engines.breathless",
    "aidm.engines.twentyfourxx",
)
# The composition root builds the installed concrete engines.
ROOTS = {"engines/registry.py"}
# Flow: core <- engines <- turn <- app <- ui.
LAYERS = ("core", "engines", "turn", "app")
# `ui` sits above them all, imports downwards, and additionally stays engine-agnostic.
TOPS = {"ui": {"aidm.engines"}}
# A framework belongs to the layers that own it and to nothing below them.
CONFINED = {
    "nicegui": ("ui",),
    "aidm.config": ("app", "ui"),
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


def _file_imports(path: Path) -> set[str]:
    imports: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
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
    violations = {
        name
        for name in _imports(package)
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


def test_no_ui_module_reaches_through_a_session_into_the_engine() -> None:
    """A bare `.engine` ban false-positives on `scenario.engine` (`ui/app.py`) and `made.engine`
    (`ui/create.py`), so this walks the attribute chain a session is reached through instead."""

    def is_session(value: ast.expr) -> bool:
        if isinstance(value, ast.Name):
            return value.id == "session"
        return (
            isinstance(value, ast.Attribute)
            and value.attr == "session"
            and isinstance(value.value, ast.Name)
            and value.value.id == "self"
        )

    naming = {
        str(path.relative_to(SOURCE))
        for path in _source_files("ui")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        if isinstance(node, ast.Attribute)
        if node.attr == "engine"
        if is_session(node.value)
    }
    assert not naming


def test_no_ui_module_names_a_built_engine_id() -> None:
    """The boundary above reads imports only; a bare id string could still smuggle world knowledge
    into `ui/` unseen, so this walks the constants themselves."""
    built_ids = {name.rsplit(".", 1)[-1] for name in ENGINES}
    naming = {
        str(path.relative_to(SOURCE))
        for path in _source_files("ui")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        if isinstance(node, ast.Constant)
        if isinstance(node.value, str) and node.value in built_ids
    }
    assert not naming
