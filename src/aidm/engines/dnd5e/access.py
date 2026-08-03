from aidm.base import EntityId
from aidm.world import ActorRecord, EntityRules, GameState, ItemRecord

from .state import Dnd5eActor, Dnd5eActorState, Dnd5eItem, Dnd5eItemState


def actor_rules(rules: EntityRules) -> Dnd5eActorState:
    """A record's rules are a union; only the tag this engine wrote narrows here."""
    if not isinstance(rules, Dnd5eActorState):
        raise ValueError(f"5e received {rules.engine!r} {type(rules).__name__}")
    return rules


def item_rules(rules: EntityRules) -> Dnd5eItemState:
    if not isinstance(rules, Dnd5eItemState):
        raise ValueError(f"5e received {rules.engine!r} {type(rules).__name__}")
    return rules


def dnd5e_actor(record: ActorRecord) -> Dnd5eActor:
    return Dnd5eActor(entity=record.entity, state=actor_rules(record.rules))


def dnd5e_item(record: ItemRecord) -> Dnd5eItem:
    return Dnd5eItem(entity=record.entity, state=item_rules(record.rules))


def actor_of(state: GameState, actor_id: EntityId) -> Dnd5eActor:
    return dnd5e_actor(state.world.actor(actor_id))


def item_of(state: GameState, item_id: EntityId) -> Dnd5eItem:
    return dnd5e_item(state.world.item(item_id))


def carried_by(state: GameState, actor_id: EntityId) -> tuple[Dnd5eItem, ...]:
    return tuple(dnd5e_item(record) for record in state.world.carried_by(actor_id))
