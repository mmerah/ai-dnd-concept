from aidm.domain.base import PLAYER_ID, EntityId
from aidm.domain.definitions import CharacterEngineData, for_engine, for_engine_or_none
from aidm.domain.entities import ActorEntity, ItemEntity
from aidm.domain.state import AuthoredWorld

from .domain.models.stats import StatBlock
from .engine import bestiary, progression
from .engine.ruleset import Ruleset
from .models import (
    Dnd5eActorDefinition,
    Dnd5eActorState,
    Dnd5eCharacterData,
    Dnd5eItemDefinition,
    Dnd5eItemState,
    Dnd5eState,
)


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
