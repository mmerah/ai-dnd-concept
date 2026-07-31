from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from aidm.base import PLAYER_ID, ActorEntity, EngineId, EntityId, ItemEntity
from aidm.content import AuthoredWorld, CharacterEngineData, for_engine, for_engine_or_none

from . import bestiary, progression
from .advancement import Dnd5eAdvancement
from .content.library import load
from .content.pack_ruleset import compile_ruleset
from .director import Dnd5eDirector
from .presentation import Dnd5ePresentation
from .rules import Dnd5eRules
from .ruleset import Ruleset
from .state import (
    Dnd5eActorDefinition,
    Dnd5eActorState,
    Dnd5eCharacterData,
    Dnd5eItemDefinition,
    Dnd5eItemState,
    Dnd5eState,
    StatBlock,
)

SHIPPED_PACK = Path(__file__).parent / "data" / "srd-2014"
ENGINE_ID: EngineId = "dnd5e"


class Dnd5eLifecycle:
    def __init__(self, ruleset: Ruleset) -> None:
        self._ruleset = ruleset

    def initialise(self, authored: AuthoredWorld, character: CharacterEngineData) -> Dnd5eState:
        sheet = for_engine(character, Dnd5eCharacterData)
        start = progression.first_level(sheet, self._ruleset)
        actors: dict[EntityId, Dnd5eActorState] = {
            PLAYER_ID: Dnd5eActorState(
                stats=StatBlock(
                    attributes=start.attributes, max_hp=start.hp_gain, hp=start.hp_gain
                ),
                progression=start.progression,
            )
        }
        items: dict[EntityId, Dnd5eItemState] = {}
        for entity in authored.world.entities.values():
            data = authored.engine_data.get(entity.id)
            if isinstance(entity, ActorEntity) and entity.id != PLAYER_ID:
                actor = for_engine_or_none(data, Dnd5eActorDefinition)
                actors[entity.id] = bestiary.statted_actor(entity.id, actor, self._ruleset)
            elif isinstance(entity, ItemEntity):
                item = for_engine_or_none(data, Dnd5eItemDefinition)
                items[entity.id] = bestiary.statted_item(entity.id, item, self._ruleset)
        return Dnd5eState(actors=actors, items=items)


@dataclass(frozen=True, slots=True)
class Dnd5eEngine:
    lifecycle: Dnd5eLifecycle
    rules: Dnd5eRules
    director: Dnd5eDirector
    presentation: Dnd5ePresentation
    advancement: Dnd5eAdvancement
    id: ClassVar[EngineId] = ENGINE_ID


def build_dnd5e_engine(pack_paths: Sequence[Path] | None = None) -> Dnd5eEngine:
    ruleset = compile_ruleset(load((SHIPPED_PACK,) if pack_paths is None else tuple(pack_paths)))
    return dnd5e_engine(ruleset)


def dnd5e_engine(ruleset: Ruleset) -> Dnd5eEngine:
    rules = Dnd5eRules(ruleset)
    return Dnd5eEngine(
        lifecycle=Dnd5eLifecycle(ruleset),
        rules=rules,
        director=Dnd5eDirector(rules),
        presentation=Dnd5ePresentation(ruleset),
        advancement=Dnd5eAdvancement(ruleset),
    )
