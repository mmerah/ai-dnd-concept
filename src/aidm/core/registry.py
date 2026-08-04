from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module

from .base import EngineId
from .config import Settings
from .engine import Engine

ENGINE_MODULES: tuple[str, ...] = (
    "aidm.engines.story.engine",
    "aidm.engines.dnd5e.engine",
)
PLUGIN = "PLUGIN"


@dataclass(frozen=True, slots=True)
class EnginePlugin:
    id: EngineId
    build: Callable[[Settings], Engine]
    badge: tuple[str, str]
    """Label and colour: the only thing the UI needs to know about a ruleset it cannot name."""


def plugins() -> tuple[EnginePlugin, ...]:
    """Imported by name, because a static import would put core back inside the engine packages."""
    found = tuple(_plugin(module) for module in ENGINE_MODULES)
    if len({plugin.id for plugin in found}) != len(found):
        raise ValueError(f"engine ids collide: {[plugin.id for plugin in found]}")
    return found


def engine_ids() -> tuple[EngineId, ...]:
    return tuple(plugin.id for plugin in plugins())


def plugin_for(engine_id: EngineId) -> EnginePlugin:
    found = next((plugin for plugin in plugins() if plugin.id == engine_id), None)
    if found is None:
        raise ValueError(f"unknown engine {engine_id!r}")
    return found


def build_engine(engine_id: EngineId, config: Settings) -> Engine:
    return plugin_for(engine_id).build(config)


def as_engine_id(value: str) -> EngineId:
    """Narrow a routed string, so an unknown engine cannot reach a filename downstream."""
    return plugin_for(EngineId(value)).id


def _plugin(module: str) -> EnginePlugin:
    declared = getattr(import_module(module), PLUGIN, None)
    if not isinstance(declared, EnginePlugin):
        raise ValueError(f"engine module {module!r} declares no {PLUGIN}")
    return declared
