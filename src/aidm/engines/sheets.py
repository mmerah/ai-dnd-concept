from abc import ABC
from collections.abc import Mapping
from typing import Self

from pydantic import Field, JsonValue

from aidm.state.model import (
    PLAYER_ID,
    Counter,
    EngineId,
    Entity,
    EntityId,
    Fact,
    Game,
    Mutable,
    WorldState,
)


class SheetBase(Mutable, ABC):
    """One actor's mechanics, whatever this engine's rules make of them."""


class SheetMechanics[S: SheetBase](Mutable):
    sheets: dict[EntityId, S] = Field(default_factory=dict)
    # How many chapters the fiction has closed, game-wide: what advancement is owed against.
    completed: Counter = Counter(current=0)

    @classmethod
    def of(cls, state: Game) -> Self:
        mechanics = state.mechanics
        if not isinstance(mechanics, cls):
            # Both engines name their model `Mechanics`, so only the module tells them apart.
            raise ValueError(
                f"the state carries {type(mechanics).__module__} mechanics, not {cls.__module__}"
            )
        return mechanics


def actor_sheets[S: Mutable](
    world: WorldState, player_rules: dict[str, JsonValue], sheet: type[S]
) -> dict[EntityId, S]:
    return {
        entity.id: sheet.model_validate(player_rules if entity.id == PLAYER_ID else {})
        for entity in world.of_kind("actor")
    }


def check_sheets(world: WorldState, sheets: Mapping[EntityId, object], engine: EngineId) -> None:
    if PLAYER_ID not in sheets:
        raise ValueError(f"the {engine} mechanics name no player")
    actors = {entity.id for entity in world.of_kind("actor")}
    if missing := sorted(actors - set(sheets)):
        raise ValueError(f"actors carry no character sheet: {missing}")
    if gone := sorted(set(sheets) - world.all_ids()):
        raise ValueError(f"mechanics name actors the world does not hold: {gone}")


def require_sheet[S](sheets: Mapping[EntityId, S], actor: Entity) -> S:
    sheet = sheets.get(actor.id)
    if sheet is None:
        raise ValueError(f"{actor.name} has no character sheet")
    return sheet


def complete_chapter(draft: Game, ending: str) -> list[Fact]:
    SheetMechanics.of(draft).completed.current += 1
    return [Fact(kind="chapter_completed", trace=ending, narrator=ending)]
