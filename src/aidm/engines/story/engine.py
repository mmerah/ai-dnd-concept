from aidm.base import Entity, EntityId
from aidm.content import AuthoredEntity, AuthoredWorld, Rules, compose_world
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


def _no_location_rules(entity_id: EntityId, rules: Rules) -> None:
    if rules:
        raise ValueError(f"location {entity_id!r} carries Story rules, but Story defines none")


def _entity_rules(authored: AuthoredEntity) -> Rules:
    """An empty payload validates into the same defaults an unauthored entity would have taken."""
    match authored.entity.kind:
        case "actor":
            return (
                StoryActorDefinition.model_validate(authored.rules)
                .runtime()
                .model_dump(mode="json")
            )
        case "item":
            return (
                StoryItemDefinition.model_validate(authored.rules).runtime().model_dump(mode="json")
            )
        case "location":
            _no_location_rules(authored.entity.id, authored.rules)
            return {}


def _initial_world(authored: AuthoredWorld, character: Rules) -> WorldState:
    sheet = StoryCharacterData.model_validate(character)
    player = StoryActorState(
        approaches=sheet.approaches,
        tags=sheet.tags,
        max_stress=sheet.max_stress,
    )
    return compose_world(authored, player.model_dump(mode="json"), _entity_rules)


def _validate_state(state: GameState) -> None:
    """Replaces core's deleted `_require_one_engine`: a foreign or malformed payload breaks here,
    not mid-combat."""
    if state.engine != ENGINE_ID:
        raise ValueError(f"Story received a {state.engine!r} game")
    for record in state.world.records.values():
        match record.entity.kind:
            case "actor":
                actor_state(record.rules)
            case "item":
                item_state(record.rules)
            case "location":
                _no_location_rules(record.entity.id, record.rules)


def _default_rules(entity: Entity) -> Rules:
    match entity.kind:
        case "actor":
            return StoryActorState(approaches=DEFAULT_APPROACHES).model_dump(mode="json")
        case "item":
            return StoryItemState().model_dump(mode="json")
        case "location":
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
        advancement_status=advancement.status,
        advancement_form=advancement.form,
        advancement_review=advancement.review,
        director_output=director.output(),
        director_instructions=director.instructions(),
        entity_state=presentation.entity_state,
    )


PLUGIN = EnginePlugin(
    id=ENGINE_ID,
    build=lambda _: build_story_engine(),
    badge=("STORY", "deep-purple-6"),
)
