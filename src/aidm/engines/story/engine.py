from dataclasses import dataclass
from typing import ClassVar

from aidm.base import PLAYER_ID, ActorEntity, EngineId, EntityId, ItemEntity
from aidm.content import AuthoredWorld, CharacterEngineData, for_engine, for_engine_or_none

from .advancement import StoryAdvancement
from .director import StoryDirector
from .presentation import StoryPresentation
from .rules import StoryRules
from .state import (
    DEFAULT_APPROACHES,
    StoryActorDefinition,
    StoryActorState,
    StoryCharacterData,
    StoryItemDefinition,
    StoryItemState,
    StoryState,
)

ENGINE_ID: EngineId = "story"


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


@dataclass(frozen=True, slots=True)
class StoryEngine:
    lifecycle: StoryLifecycle
    rules: StoryRules
    director: StoryDirector
    presentation: StoryPresentation
    advancement: StoryAdvancement
    id: ClassVar[EngineId] = ENGINE_ID


def build_story_engine() -> StoryEngine:
    rules = StoryRules()
    return StoryEngine(
        lifecycle=StoryLifecycle(),
        rules=rules,
        director=StoryDirector(rules),
        presentation=StoryPresentation(),
        advancement=StoryAdvancement(),
    )
