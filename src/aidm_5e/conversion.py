
from aidm.domain.base import EntityId
from aidm.domain.engine import EngineData
from aidm.domain.entities import (
    ActorEntity,
    Entity,
    EntityDetail,
    ItemEntity,
    LocationEntity,
)
from aidm.domain.events import (
    ActorMoved,
    EntityCreated,
    EntityDiscovered,
    Event,
    ItemMoved,
)
from aidm.domain.state import GameState

from .codecs import ACTOR_STATE_CODEC, ITEM_STATE_CODEC
from .constants import ENGINE_ID, SCHEMA_VERSION
from .domain.models.base import EntityId as LegacyEntityId
from .domain.models.entities import (
    ActorEntity as LegacyActor,
)
from .domain.models.entities import (
    Entity as LegacyEntity,
)
from .domain.models.entities import (
    EntityDetail as LegacyDetail,
)
from .domain.models.entities import (
    ItemEntity as LegacyItem,
)
from .domain.models.entities import (
    LocationEntity as LegacyLocation,
)
from .domain.models.events import (
    EntityCreated as LegacyEntityCreated,
)
from .domain.models.events import (
    EntityDiscovered as LegacyEntityDiscovered,
)
from .domain.models.events import (
    Event as LegacyEvent,
)
from .domain.models.events import (
    ItemMoved as LegacyItemMoved,
)
from .domain.models.events import (
    Moved as LegacyMoved,
)
from .domain.models.state import (
    Exchange as LegacyExchange,
)
from .domain.models.state import (
    GameState as LegacyGameState,
)
from .domain.models.state import (
    ScenarioMeta as LegacyScenarioMeta,
)
from .domain.models.state import (
    WorldState as LegacyWorld,
)
from .events import DND5E_EVENT_ADAPTER, Dnd5eRuleEvent, encode_dnd5e_event
from .models import Dnd5eActorState, Dnd5eItemState


def to_legacy_state(state: GameState) -> LegacyGameState:
    entities = {
        LegacyEntityId(str(entity.id)): _to_legacy_entity(entity)
        for entity in state.world.entities.values()
    }
    return LegacyGameState(
        scenario=LegacyScenarioMeta(
            title=state.scenario.title,
            premise=state.scenario.premise,
        ),
        world=LegacyWorld(entities=entities),
        history=[
            LegacyExchange(prompt=exchange.prompt, narration=exchange.narration)
            for exchange in state.history
        ],
        turn=state.turn,
    )


def _to_legacy_entity(entity: Entity) -> LegacyEntity:
    detail = (
        None
        if entity.detail is None
        else LegacyDetail(
            description=entity.detail.description,
            hook=entity.detail.hook,
        )
    )
    common = {
        "id": LegacyEntityId(str(entity.id)),
        "name": entity.name,
        "brief": entity.brief,
        "detail": detail,
        "known": entity.known,
        "authored": entity.authored,
    }
    match entity:
        case ActorEntity():
            if entity.rules is None:
                raise ValueError(f"5e actor {entity.id!r} has no rules data")
            actor = ACTOR_STATE_CODEC.decode(entity.rules)
            return LegacyActor.model_validate(
                common
                | {
                    "location_id": LegacyEntityId(str(entity.location_id)),
                    "stats": actor.stats,
                    "progression": actor.progression,
                    "ref": actor.ref,
                }
            )
        case ItemEntity():
            if entity.rules is None:
                raise ValueError(f"5e item {entity.id!r} has no rules data")
            item = ITEM_STATE_CODEC.decode(entity.rules)
            return LegacyItem.model_validate(
                common
                | {
                    "container_id": LegacyEntityId(str(entity.container_id)),
                    "ref": item.ref,
                }
            )
        case LocationEntity():
            if entity.rules is not None:
                raise ValueError(f"5e location {entity.id!r} must not have rules data")
            return LegacyLocation.model_validate(common)


def rules_for_legacy_entity(entity: LegacyEntity) -> EngineData | None:
    if isinstance(entity, LegacyActor):
        return ACTOR_STATE_CODEC.encode(
            Dnd5eActorState(
                stats=entity.stats,
                progression=entity.progression,
                ref=entity.ref,
            )
        )
    if isinstance(entity, LegacyItem):
        return ITEM_STATE_CODEC.encode(Dnd5eItemState(ref=entity.ref))
    return None


def created_from_legacy(entity: LegacyEntity) -> Entity:
    detail = (
        None
        if entity.detail is None
        else EntityDetail(
            description=entity.detail.description,
            hook=entity.detail.hook,
        )
    )
    common = {
        "id": EntityId(str(entity.id)),
        "name": entity.name,
        "brief": entity.brief,
        "detail": detail,
        "known": entity.known,
        "authored": entity.authored,
        "rules": rules_for_legacy_entity(entity),
    }
    match entity:
        case LegacyActor():
            return ActorEntity.model_validate(
                common | {"location_id": EntityId(str(entity.location_id))}
            )
        case LegacyItem():
            return ItemEntity.model_validate(
                common | {"container_id": EntityId(str(entity.container_id))}
            )
        case LegacyLocation():
            return LocationEntity.model_validate(common)


def event_from_legacy(event: LegacyEvent) -> Event:
    match event:
        case LegacyEntityCreated(entity=entity):
            return EntityCreated(entity=created_from_legacy(entity))
        case LegacyEntityDiscovered(entity_id=entity_id, name=name):
            return EntityDiscovered(entity_id=EntityId(str(entity_id)), name=name)
        case LegacyMoved(
            actor_id=actor_id,
            actor_name=actor_name,
            location_id=location_id,
            location_name=location_name,
        ):
            return ActorMoved(
                actor_id=EntityId(str(actor_id)),
                actor_name=actor_name,
                location_id=EntityId(str(location_id)),
                location_name=location_name,
            )
        case LegacyItemMoved(
            item_id=item_id,
            item_name=item_name,
            to_id=to_id,
            to_name=to_name,
            to_kind=to_kind,
        ):
            return ItemMoved(
                item_id=EntityId(str(item_id)),
                item_name=item_name,
                to_id=EntityId(str(to_id)),
                to_name=to_name,
                to_kind=to_kind,
            )
        case _:
            return encode_dnd5e_event(
                _rule_event(event),
                ENGINE_ID,
                SCHEMA_VERSION,
            )


def _rule_event(event: LegacyEvent) -> Dnd5eRuleEvent:
    return DND5E_EVENT_ADAPTER.validate_python(event)
