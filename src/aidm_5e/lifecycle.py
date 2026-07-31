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
from .conversion import rules_for_legacy_entity
from .domain.models.base import EntityId as LegacyEntityId
from .domain.models.entities import ActorEntity as LegacyActor
from .domain.models.entities import Entity as LegacyEntity
from .domain.models.entities import ItemEntity as LegacyItem
from .domain.models.entities import LocationEntity as LegacyLocation
from .domain.models.state import (
    CharacterSheet as LegacyCharacter,
)
from .domain.models.state import (
    ScenarioDef as LegacyScenario,
)
from .domain.models.state import (
    ScenarioMeta as LegacyScenarioMeta,
)
from .domain.models.state import (
    StartingItem as LegacyStartingItem,
)
from .domain.models.stats import StatBlock
from .engine import campaign
from .engine.ruleset import Ruleset
from .models import Dnd5eActorState, Dnd5eGameState, Dnd5eItemState


class Dnd5eLifecycle:
    def __init__(self, ruleset: Ruleset) -> None:
        self._ruleset = ruleset

    def initialise(
        self,
        world: WorldState,
        scenario: ScenarioDefinition,
        character: CharacterDefinition,
    ) -> EngineInitialization:
        character_data = CHARACTER_CODEC.decode(character.engine_data)
        scenario_entities = _legacy_scenario_entities(scenario)
        starting_items = tuple(
            LegacyStartingItem(
                name=item.name,
                brief=item.brief,
                ref=(
                    None
                    if item.engine_data is None
                    else ITEM_DEFINITION_CODEC.decode(item.engine_data).ref
                ),
            )
            for item in character.starting_items
        )
        legacy = campaign.begin(
            LegacyScenario(
                meta=LegacyScenarioMeta(
                    title=scenario.meta.title,
                    premise=scenario.meta.premise,
                ),
                starting_location_id=LegacyEntityId(str(scenario.starting_location_id)),
                entities=scenario_entities,
            ),
            LegacyCharacter(
                name=character.name,
                brief=character.brief,
                origin=character_data.origin,
                starting_attributes=character_data.starting_attributes,
                decisions=character_data.decisions,
                starting_items=starting_items,
            ),
            self._ruleset,
        )
        if set(map(str, legacy.world.entities)) != set(map(str, world.entities)):
            raise ValueError("5e initialization changed the core world entity ids")
        entity_rules: dict[EntityId, EngineData | None] = {
            EntityId(str(entity_id)): rules_for_legacy_entity(entity)
            for entity_id, entity in legacy.world.entities.items()
        }
        if entity_rules.get(PLAYER_ID) is None:
            raise ValueError("5e initialization did not provide player rules")
        return EngineInitialization(
            game_rules=GAME_STATE_CODEC.encode(Dnd5eGameState()),
            entity_rules=entity_rules,
        )

    def rules_for_created_entity(
        self,
        entity: Entity,
        state: GameState,
    ) -> EngineData | None:
        if state.engine != ENGINE_ID:
            raise ValueError(f"5e lifecycle cannot initialize {state.engine!r} state")
        if isinstance(entity, ActorEntity):
            return ACTOR_STATE_CODEC.encode(Dnd5eActorState(stats=StatBlock()))
        if isinstance(entity, ItemEntity):
            return ITEM_STATE_CODEC.encode(Dnd5eItemState())
        return None


def _legacy_scenario_entities(scenario: ScenarioDefinition) -> list[LegacyEntity]:
    entities: list[LegacyEntity] = []
    for definition in scenario.entities:
        common = {
            "id": definition.id,
            "kind": definition.kind,
            "name": definition.name,
            "brief": definition.brief,
            "known": definition.known,
        }
        match definition.kind:
            case "actor":
                mechanical = (
                    None
                    if definition.engine_data is None
                    else ACTOR_DEFINITION_CODEC.decode(definition.engine_data)
                )
                entities.append(
                    LegacyActor.model_validate(
                        common
                        | {
                            "location_id": definition.location_id,
                            "ref": None if mechanical is None else mechanical.ref,
                            "stats": (
                                {}
                                if mechanical is None or mechanical.stats is None
                                else mechanical.stats
                            ),
                        }
                    )
                )
            case "item":
                mechanical = (
                    None
                    if definition.engine_data is None
                    else ITEM_DEFINITION_CODEC.decode(definition.engine_data)
                )
                entities.append(
                    LegacyItem.model_validate(
                        common
                        | {
                            "container_id": definition.container_id,
                            "ref": None if mechanical is None else mechanical.ref,
                        }
                    )
                )
            case "location":
                if definition.engine_data is not None:
                    raise ValueError(f"5e location {definition.id!r} cannot have engine data")
                entities.append(LegacyLocation.model_validate(common))
    return entities
