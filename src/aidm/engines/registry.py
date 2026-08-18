from importlib import import_module

from aidm.state.base import EngineId

from .engine import Engine
from .sheets import SheetBase

ENGINE_MODULES: tuple[str, ...] = (
    "aidm.engines.loner3e.rules",
    "aidm.engines.twentyfourxx.rules",
)
ENGINE = "ENGINE"


def engines() -> tuple[type[Engine[SheetBase]], ...]:
    """Imported by name, because a static import would put core back inside the engine packages."""
    found = tuple(_engine_class(module) for module in ENGINE_MODULES)
    if len({engine.id for engine in found}) != len(found):
        raise ValueError(f"engine ids collide: {[engine.id for engine in found]}")
    return found


def engine_ids() -> tuple[EngineId, ...]:
    return tuple(engine.id for engine in engines())


def engine_class(engine_id: EngineId) -> type[Engine[SheetBase]]:
    found = next((engine for engine in engines() if engine.id == engine_id), None)
    if found is None:
        raise ValueError(f"unknown engine {engine_id!r}")
    return found


def _engine_class(module: str) -> type[Engine[SheetBase]]:
    declared = getattr(import_module(module), ENGINE, None)
    if not (isinstance(declared, type) and issubclass(declared, Engine)):
        raise ValueError(f"engine module {module!r} declares no {ENGINE}")
    # issubclass narrows only the unparameterized generic; the sheet type isn't statically knowable.
    return declared  # pyright: ignore[reportUnknownVariableType]
