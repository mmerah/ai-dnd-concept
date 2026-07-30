from aidm.engine_api.codec import EngineCodec

from .constants import ENGINE_ID, SCHEMA_VERSION
from .models import (
    StoryActorDefinition,
    StoryActorState,
    StoryCharacterData,
    StoryGameState,
    StoryItemDefinition,
    StoryItemState,
)

ACTOR_DEFINITION_CODEC = EngineCodec(
    StoryActorDefinition,
    engine=ENGINE_ID,
    schema_version=SCHEMA_VERSION,
)
ACTOR_STATE_CODEC = EngineCodec(
    StoryActorState,
    engine=ENGINE_ID,
    schema_version=SCHEMA_VERSION,
)
CHARACTER_CODEC = EngineCodec(
    StoryCharacterData,
    engine=ENGINE_ID,
    schema_version=SCHEMA_VERSION,
)
GAME_STATE_CODEC = EngineCodec(
    StoryGameState,
    engine=ENGINE_ID,
    schema_version=SCHEMA_VERSION,
)
ITEM_DEFINITION_CODEC = EngineCodec(
    StoryItemDefinition,
    engine=ENGINE_ID,
    schema_version=SCHEMA_VERSION,
)
ITEM_STATE_CODEC = EngineCodec(
    StoryItemState,
    engine=ENGINE_ID,
    schema_version=SCHEMA_VERSION,
)
