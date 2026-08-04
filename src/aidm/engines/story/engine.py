from aidm.core.base import Entity
from aidm.core.content import AuthoredEntity, AuthoredWorld, Rules, compose_world
from aidm.core.engine import Engine
from aidm.core.registry import EnginePlugin
from aidm.core.world import BareLocation

from .advancement import advance, available
from .identity import ENGINE_ID
from .presentation import StoryPresentation
from .state import (
    DEFAULT_APPROACHES,
    StoryActorDefinition,
    StoryActorState,
    StoryCharacterData,
    StoryItemDefinition,
    StoryItemState,
    StoryRules,
    StoryState,
    StoryWorldState,
)
from .tools import DIRECTOR_INSTRUCTIONS, story_toolset
from .ui import advancement_panel


def _entity_rules(authored: AuthoredEntity) -> StoryRules:
    """An empty payload validates into the same defaults an unauthored entity would have taken."""
    match authored.entity.kind:
        case "actor":
            return StoryActorDefinition.model_validate(authored.rules).runtime()
        case "item":
            return StoryItemDefinition.model_validate(authored.rules).runtime()
        case "location":
            return BareLocation.model_validate(authored.rules)


def _initial_world(authored: AuthoredWorld, character: Rules) -> StoryWorldState:
    sheet = StoryCharacterData.model_validate(character)
    player = StoryActorState(
        approaches=sheet.approaches,
        tags=sheet.tags,
        max_stress=sheet.max_stress,
    )
    return compose_world(StoryWorldState, authored, player, _entity_rules)


def _default_rules(entity: Entity) -> StoryRules:
    match entity.kind:
        case "actor":
            return StoryActorState(approaches=DEFAULT_APPROACHES)
        case "item":
            return StoryItemState()
        case "location":
            return BareLocation()


def build_story_engine() -> Engine[StoryRules]:
    return Engine(
        id=ENGINE_ID,
        state_type=StoryState,
        initial_world=_initial_world,
        validate_state=lambda state: None,
        default_rules=_default_rules,
        advance=advance,
        advancement_available=available,
        advancement_panel=advancement_panel,
        toolsets={"director": story_toolset()},
        director_instructions=DIRECTOR_INSTRUCTIONS,
        entity_state=StoryPresentation().entity_state,
    )


PLUGIN = EnginePlugin(
    id=ENGINE_ID,
    build=lambda _: build_story_engine(),
    badge=("STORY", "deep-purple-6"),
)
