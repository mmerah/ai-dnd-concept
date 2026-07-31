from aidm.domain.engine import EngineCodec

from .constants import ENGINE_ID, SCHEMA_VERSION
from .models import (
    Dnd5eActorDefinition,
    Dnd5eActorState,
    Dnd5eCharacterData,
    Dnd5eGameState,
    Dnd5eItemDefinition,
    Dnd5eItemState,
)

ACTOR_DEFINITION_CODEC = EngineCodec(
    Dnd5eActorDefinition,
    engine=ENGINE_ID,
    schema_version=SCHEMA_VERSION,
)
ACTOR_STATE_CODEC = EngineCodec(
    Dnd5eActorState,
    engine=ENGINE_ID,
    schema_version=SCHEMA_VERSION,
)
CHARACTER_CODEC = EngineCodec(
    Dnd5eCharacterData,
    engine=ENGINE_ID,
    schema_version=SCHEMA_VERSION,
)
GAME_STATE_CODEC = EngineCodec(
    Dnd5eGameState,
    engine=ENGINE_ID,
    schema_version=SCHEMA_VERSION,
)
ITEM_DEFINITION_CODEC = EngineCodec(
    Dnd5eItemDefinition,
    engine=ENGINE_ID,
    schema_version=SCHEMA_VERSION,
)
ITEM_STATE_CODEC = EngineCodec(
    Dnd5eItemState,
    engine=ENGINE_ID,
    schema_version=SCHEMA_VERSION,
)
