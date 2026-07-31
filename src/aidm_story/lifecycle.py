from aidm.domain.base import PLAYER_ID, EntityId
from aidm.domain.definitions import CharacterDefinition, ScenarioDefinition
from aidm.domain.engine import EngineData, EngineInitialization
from aidm.domain.entities import ActorEntity, Entity, ItemEntity
from aidm.domain.state import GameState, WorldState

from .codecs import (
    ACTOR_DEFINITION_CODEC,
    ACTOR_STATE_CODEC,
    CHARACTER_CODEC,
    GAME_STATE_CODEC,
    ITEM_DEFINITION_CODEC,
    ITEM_STATE_CODEC,
)
from .constants import ENGINE_ID
from .models import DEFAULT_APPROACHES, StoryActorState, StoryGameState, StoryItemState


class StoryLifecycle:
    def initialise(
        self,
        world: WorldState,
        scenario: ScenarioDefinition,
        character: CharacterDefinition,
    ) -> EngineInitialization:
        character_data = CHARACTER_CODEC.decode(character.engine_data)
        character_state = StoryActorState(
            approaches=character_data.approaches,
            tags=character_data.tags,
            max_stress=character_data.max_stress,
        )
        scenario_definitions = {definition.id: definition for definition in scenario.entities}
        starting_items = {item.name: item for item in character.starting_items}
        if len(starting_items) != len(character.starting_items):
            raise ValueError("starting item names must be unique")
        rules: dict[EntityId, EngineData | None] = {}
        for entity in world.entities.values():
            if entity.id == PLAYER_ID:
                rules[entity.id] = ACTOR_STATE_CODEC.encode(character_state)
                continue
            definition = scenario_definitions.get(entity.id)
            if isinstance(entity, ActorEntity):
                actor = (
                    StoryActorState(approaches=DEFAULT_APPROACHES)
                    if definition is None or definition.engine_data is None
                    else ACTOR_DEFINITION_CODEC.decode(definition.engine_data).runtime()
                )
                rules[entity.id] = ACTOR_STATE_CODEC.encode(actor)
            elif isinstance(entity, ItemEntity):
                data = definition.engine_data if definition is not None else None
                if definition is None:
                    item = starting_items.pop(entity.name, None)
                    if item is None:
                        raise ValueError(f"cannot match starting item rules for {entity.name!r}")
                    data = item.engine_data
                item_state = (
                    StoryItemState()
                    if data is None
                    else ITEM_DEFINITION_CODEC.decode(data).runtime()
                )
                rules[entity.id] = ITEM_STATE_CODEC.encode(item_state)
            else:
                if definition is not None and definition.engine_data is not None:
                    raise ValueError(
                        f"Story location {entity.id!r} cannot have engine definition data"
                    )
                rules[entity.id] = None
        if starting_items:
            raise ValueError(f"unmatched starting items: {sorted(starting_items)}")
        return EngineInitialization(
            game_rules=GAME_STATE_CODEC.encode(StoryGameState()),
            entity_rules=rules,
        )

    def rules_for_created_entity(
        self,
        entity: Entity,
        state: GameState,
    ) -> EngineData | None:
        if state.engine != ENGINE_ID:
            raise ValueError(f"Story lifecycle cannot initialize {state.engine!r} state")
        if isinstance(entity, ActorEntity):
            return ACTOR_STATE_CODEC.encode(StoryActorState(approaches=DEFAULT_APPROACHES))
        if isinstance(entity, ItemEntity):
            return ITEM_STATE_CODEC.encode(StoryItemState())
        return None
