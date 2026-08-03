from aidm.base import PLAYER_ID, ActorEntity, EntityId, ItemEntity
from aidm.world import EntityRules, GameState

from .state import StoryActorState, StoryItemState


def actor_rules(rules: EntityRules) -> StoryActorState:
    """A record's rules are a union; only the tag this engine wrote narrows here."""
    if not isinstance(rules, StoryActorState):
        raise ValueError(f"Story received {rules.engine!r} {type(rules).__name__}")
    return rules


def item_rules(rules: EntityRules) -> StoryItemState:
    if not isinstance(rules, StoryItemState):
        raise ValueError(f"Story received {rules.engine!r} {type(rules).__name__}")
    return rules


def actor_of(state: GameState, actor_id: EntityId) -> tuple[ActorEntity, StoryActorState]:
    record = state.world.actor(actor_id)
    return record.entity, actor_rules(record.rules)


def item_of(state: GameState, item_id: EntityId) -> tuple[ItemEntity, StoryItemState]:
    record = state.world.item(item_id)
    return record.entity, item_rules(record.rules)


def player_rules(state: GameState) -> StoryActorState:
    return actor_rules(state.world.actor(PLAYER_ID).rules)
