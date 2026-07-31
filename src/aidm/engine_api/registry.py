from ..domain.base import Slug
from ..domain.engine import EngineRef
from .contracts import EngineDescriptor, EngineFactory, RulesEngine


class EngineRegistry:
    def __init__(self) -> None:
        self._entries: dict[Slug, tuple[EngineDescriptor, EngineFactory]] = {}
        self._instances: dict[Slug, RulesEngine] = {}

    def register(self, descriptor: EngineDescriptor, factory: EngineFactory) -> None:
        engine_id = descriptor.ref.id
        if engine_id in self._entries:
            raise ValueError(f"engine id {engine_id!r} is already registered")
        self._entries[engine_id] = (descriptor, factory)

    def require(self, requested: EngineRef) -> RulesEngine:
        entry = self._entries.get(requested.id)
        if entry is None:
            available = sorted(self._entries)
            raise ValueError(f"engine {requested.id!r} is not installed; available: {available}")
        descriptor, factory = entry
        if descriptor.ref != requested:
            raise ValueError(
                f"requested engine is {requested.model_dump()}, "
                f"installed engine is {descriptor.ref.model_dump()}"
            )
        existing = self._instances.get(requested.id)
        if existing is not None:
            return existing
        engine = factory()
        constructed = EngineDescriptor.from_stamp(engine.stamp)
        if constructed != descriptor:
            raise ValueError(
                f"constructed engine descriptor {constructed.model_dump()} "
                f"does not match registration {descriptor.model_dump()}"
            )
        self._instances[requested.id] = engine
        return engine
