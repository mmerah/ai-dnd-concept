from abc import ABC
from collections.abc import Mapping

from pydantic import Field, JsonValue

from aidm.state.base import PLAYER_ID, EngineId, Entity, EntityId, Mutable
from aidm.state.world import GameState, WorldState


class SheetBase(Mutable, ABC):
    """One actor's mechanics, whatever this engine's rules make of them."""


class SheetMechanics[S: SheetBase](Mutable):
    sheets: dict[EntityId, S] = Field(default_factory=dict)


def actor_sheets[S: Mutable](
    state: GameState,
    rules: Mapping[EntityId, dict[str, JsonValue]],
    sheet: type[S],
    engine: EngineId,
) -> dict[EntityId, S]:
    sheets: dict[EntityId, S] = {}
    for entity in state.world.entities.values():
        authored = rules.get(entity.id)
        if entity.kind != "actor":
            if authored:
                raise ValueError(f"{engine} writes mechanics for actors only, not {entity.id!r}")
            continue
        sheets[entity.id] = sheet.model_validate(authored or {})
    return sheets


def check_sheets(state: GameState, sheets: Mapping[EntityId, object], engine: EngineId) -> None:
    if PLAYER_ID not in sheets:
        raise ValueError(f"the {engine} mechanics name no player")
    actors = {entity.id for entity in state.world.of_kind("actor")}
    if missing := sorted(actors - set(sheets)):
        raise ValueError(f"actors carry no character sheet: {missing}")
    if gone := sorted(set(sheets) - state.world.all_ids()):
        raise ValueError(f"mechanics name actors the world does not hold: {gone}")


def require_sheet[S](sheets: Mapping[EntityId, S], actor: Entity) -> S:
    sheet = sheets.get(actor.id)
    if sheet is None:
        raise ValueError(f"{actor.name} has no character sheet")
    return sheet


def resolved_threads(world: WorldState) -> int:
    return sum(1 for thread in world.threads.values() if thread.status == "resolved")
