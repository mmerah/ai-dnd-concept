from ..domain.base import SAVE_VERSION
from ..domain.definitions import CharacterDefinition, ScenarioDefinition
from ..domain.engine import EngineRef, EngineStamp
from ..domain.state import GameState

_STAMP_FIELDS = ("id", "rules_version", "schema_version", "dependencies")


def save_mismatches(
    state: GameState,
    scenario: ScenarioDefinition,
    character: CharacterDefinition,
) -> tuple[str, ...]:
    problems: list[str] = []
    if state.version != SAVE_VERSION:
        problems.append(f"save version is {state.version}, this build needs {SAVE_VERSION}")
    if state.scenario != scenario.meta:
        problems.append(
            f"save scenario is {state.scenario.title!r}, "
            f"selected scenario is {scenario.meta.title!r}"
        )
    if state.player.name != character.name or state.player.brief != character.brief:
        problems.append(
            f"save player is {state.player.name!r}, selected character is {character.name!r}"
        )
    saved_ref = EngineRef(id=state.engine.id, rules_version=state.engine.rules_version)
    if saved_ref != scenario.engine:
        problems.append(f"save engine is {saved_ref!r}, selected engine is {scenario.engine!r}")
    return tuple(problems)


def stamp_mismatches(state: GameState, stamp: EngineStamp) -> tuple[str, ...]:
    if state.engine == stamp:
        return ()
    problems = tuple(
        f"save engine {name} is {getattr(state.engine, name)!r}, "
        f"selected engine {name} is {getattr(stamp, name)!r}"
        for name in _STAMP_FIELDS
        if getattr(state.engine, name) != getattr(stamp, name)
    )
    return problems or ("save engine stamp does not match selected engine",)
