from aidm.engines.engine import Engine
from aidm.engines.loner3e.rules import Loner3eEngine
from aidm.engines.sheets import SheetBase
from aidm.engines.twentyfourxx.rules import TwentyfourxxEngine
from aidm.state.base import EngineId

# Engine's sheet type param is invariant, so each concrete engine's own sheet type doesn't
# statically widen to SheetBase here even though every engine satisfies the bound.
ENGINES: tuple[type[Engine[SheetBase]], ...] = (
    Loner3eEngine,  # pyright: ignore[reportAssignmentType]
    TwentyfourxxEngine,  # pyright: ignore[reportAssignmentType]
)


def engine_ids() -> tuple[EngineId, ...]:
    return tuple(engine.id for engine in ENGINES)


def engine_class(engine_id: EngineId) -> type[Engine[SheetBase]]:
    found = next((engine for engine in ENGINES if engine.id == engine_id), None)
    if found is None:
        raise ValueError(f"unknown engine {engine_id!r}")
    return found
