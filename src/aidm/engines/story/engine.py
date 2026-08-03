from aidm.base import ActorEntity, Entity, ItemEntity, LocationEntity
from aidm.content import AuthoredActor, AuthoredItem, AuthoredWorld, Rules, compose_world
from aidm.engine import Engine
from aidm.registry import EnginePlugin
from aidm.world import GameState, WorldState

from .access import actor_state, item_state
from .advancement import StoryAdvancement
from .director import StoryDirector
from .identity import ENGINE_ID
from .presentation import StoryPresentation
from .rules import StoryRules
from .state import (
    DEFAULT_APPROACHES,
    StoryActorDefinition,
    StoryActorState,
    StoryCharacterData,
    StoryItemDefinition,
    StoryItemState,
)


def _actor_rules(authored: AuthoredActor) -> Rules:
    """An empty payload validates into the same defaults an unauthored actor would have taken."""
    return StoryActorDefinition.model_validate(authored.rules).runtime().model_dump(mode="json")


def _item_rules(authored: AuthoredItem) -> Rules:
    return StoryItemDefinition.model_validate(authored.rules).runtime().model_dump(mode="json")


def _initial_world(authored: AuthoredWorld, character: Rules) -> WorldState:
    sheet = StoryCharacterData.model_validate(character)
    player = StoryActorState(
        approaches=sheet.approaches,
        tags=sheet.tags,
        max_stress=sheet.max_stress,
    )
    return compose_world(authored, player.model_dump(mode="json"), _actor_rules, _item_rules)


def _validate_state(state: GameState) -> None:
    """Replaces core's deleted `_require_one_engine`: a foreign or malformed payload breaks here,
    not mid-combat."""
    if state.engine != ENGINE_ID:
        raise ValueError(f"Story received a {state.engine!r} game")
    for record in state.world.actors.values():
        actor_state(record.rules)
    for record in state.world.items.values():
        item_state(record.rules)


def _default_rules(entity: Entity) -> Rules:
    match entity:
        case ActorEntity():
            return StoryActorState(approaches=DEFAULT_APPROACHES).model_dump(mode="json")
        case ItemEntity():
            return StoryItemState().model_dump(mode="json")
        case LocationEntity():
            return {}


def build_story_engine() -> Engine:
    rules = StoryRules()
    director = StoryDirector(rules)
    presentation = StoryPresentation()
    advancement = StoryAdvancement()
    return Engine(
        id=ENGINE_ID,
        initial_world=_initial_world,
        validate_state=_validate_state,
        default_rules=_default_rules,
        resolve=rules.resolve,
        advance=advancement.advance,
        advancement_available=advancement.available,
        director_output=director.output(),
        director_instructions=director.instructions(),
        entity_state=presentation.entity_state,
        advancement=advancement,
    )


PLUGIN = EnginePlugin(
    id=ENGINE_ID,
    build=lambda _: build_story_engine(),
    badge=("STORY", "deep-purple-6"),
)
