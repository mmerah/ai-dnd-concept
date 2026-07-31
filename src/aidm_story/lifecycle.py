from aidm.domain.base import PLAYER_ID, EntityId
from aidm.domain.definitions import CharacterEngineData, for_engine, for_engine_or_none
from aidm.domain.entities import ActorEntity, ItemEntity
from aidm.domain.state import AuthoredWorld

from .models import (
    DEFAULT_APPROACHES,
    StoryActorDefinition,
    StoryActorState,
    StoryCharacterData,
    StoryItemDefinition,
    StoryItemState,
    StoryState,
)


class StoryLifecycle:
    @staticmethod
    def initialise(authored: AuthoredWorld, character: CharacterEngineData) -> StoryState:
        sheet = for_engine(character, StoryCharacterData)
        actors: dict[EntityId, StoryActorState] = {
            PLAYER_ID: StoryActorState(
                approaches=sheet.approaches,
                tags=sheet.tags,
                max_stress=sheet.max_stress,
            )
        }
        items: dict[EntityId, StoryItemState] = {}
        for entity in authored.world.entities.values():
            data = authored.engine_data.get(entity.id)
            if isinstance(entity, ActorEntity) and entity.id != PLAYER_ID:
                actor = for_engine_or_none(data, StoryActorDefinition)
                actors[entity.id] = (
                    StoryActorState(approaches=DEFAULT_APPROACHES)
                    if actor is None
                    else actor.runtime()
                )
            elif isinstance(entity, ItemEntity):
                item = for_engine_or_none(data, StoryItemDefinition)
                items[entity.id] = StoryItemState() if item is None else item.runtime()
        return StoryState(actors=actors, items=items)
