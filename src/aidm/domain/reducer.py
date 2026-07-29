from collections.abc import Mapping, Sequence
from functools import reduce

from ..content.records.base import ContentRef
from ..utils.models import updated
from .models.base import EntityId
from .models.entities import ActorEntity, Entity, ItemEntity, LocationEntity
from .models.events import (
    AttackRolled,
    ConditionChanged,
    DcRolled,
    DiceRolled,
    EntityCreated,
    EntityDiscovered,
    Event,
    FeatureActivated,
    FeatureUsed,
    HpChanged,
    ItemMoved,
    LeveledUp,
    LevelUpAvailable,
    Moved,
    PoolRefilled,
    Rested,
)
from .models.progression import (
    Advancement,
    FeatureKey,
    FeatureResourceState,
    Progression,
    feature_key,
)
from .models.state import GameState


def _replacing(state: GameState, entity: Entity) -> GameState:
    return updated(state, world=state.world.replacing(entity))


def _move_actor(state: GameState, actor_id: EntityId, location_id: EntityId) -> GameState:
    world = state.world
    world.require_kind(location_id, LocationEntity)
    moved = updated(world.require_kind(actor_id, ActorEntity), location_id=location_id)
    return _replacing(state, moved)


def _move_item(state: GameState, item_id: EntityId, to_id: EntityId) -> GameState:
    world = state.world
    item = world.require_kind(item_id, ItemEntity)
    if not isinstance(world.require(to_id), ActorEntity | LocationEntity):
        raise ValueError(f"cannot move {item_id!r} to {to_id!r}: it holds nothing")
    return _replacing(state, updated(item, container_id=to_id))


def _apply_one(state: GameState, event: Event) -> GameState:
    world = state.world
    match event:
        case DcRolled() | DiceRolled() | AttackRolled() | FeatureActivated():
            return state  # branches carry effects; rolls are evidence
        case ItemMoved(item_id=item_id, to_id=to_id):
            return _move_item(state, item_id, to_id)
        case HpChanged(target_id=target_id, delta=delta):
            actor = world.require_kind(target_id, ActorEntity)
            return _replacing(state, updated(actor, stats=actor.stats.with_hp_delta(delta)))
        case ConditionChanged(target_id=target_id, condition=condition, active=active):
            actor = world.require_kind(target_id, ActorEntity)
            stats = actor.stats.with_condition(condition, active=active)
            return _replacing(state, updated(actor, stats=stats))
        case Moved(actor_id=actor_id, location_id=location_id):
            return _move_actor(state, actor_id, location_id)
        case EntityDiscovered(entity_id=entity_id):
            return _replacing(state, updated(world.require(entity_id), known=True))
        case LevelUpAvailable():
            player = state.player
            progression = player.progression
            if progression is None:
                raise ValueError("the player has no progression to unlock")
            return _replacing(
                state,
                updated(player, progression=updated(progression, level_up_available=True)),
            )
        case FeatureUsed(ref=ref, spent=spent, remaining=remaining, maximum=maximum):
            return _spent(state, ref, spent=spent, remaining=remaining, maximum=maximum)
        case Rested(refilled=refilled):
            return _refilled(state, refilled)
        case LeveledUp(advancement=advancement):
            return _grown(state, advancement)
        case EntityCreated(entity=entity):
            return updated(state, world=world.adding(entity))


def _grown(state: GameState, advancement: Advancement) -> GameState:
    """Require the next level because applying an HP gain twice is not idempotent."""
    player = state.player
    held = player.progression
    reached = advancement.progression.level
    if held is None or reached != held.level + 1:
        raise ValueError(f"cannot reach level {reached} from {held.level if held else 'no class'}")
    stats = updated(
        player.stats,
        attributes=advancement.attributes,
        max_hp=player.stats.max_hp + advancement.hp_gain,
        hp=player.stats.hp + advancement.hp_gain,
    )
    return _replacing(state, updated(player, stats=stats, progression=advancement.progression))


def _progression(state: GameState) -> Progression:
    progression = state.player.progression
    if progression is None:
        raise ValueError("the player has no feature resources")
    return progression


def _with_resources(
    state: GameState, resources: Mapping[FeatureKey, FeatureResourceState]
) -> GameState:
    player = state.player
    progression = _progression(state)
    return _replacing(
        state, updated(player, progression=updated(progression, feature_resources=resources))
    )


def _spent(
    state: GameState, ref: ContentRef, *, spent: int, remaining: int, maximum: int
) -> GameState:
    key = feature_key(ref)
    held = _progression(state).feature_resources
    before = held.get(key)
    if before is None or maximum != before.maximum or remaining != before.remaining - spent:
        raise ValueError(
            f"cannot spend {spent} from {ref.index!r} resource {before} to {remaining}/{maximum}"
        )
    return _with_resources(state, {**held, key: updated(before, remaining=remaining)})


def _refilled(state: GameState, refilled: Sequence[PoolRefilled]) -> GameState:
    resources = dict(_progression(state).feature_resources)
    for pool in refilled:
        key = feature_key(pool.ref)
        before = resources.get(key)
        if before is None or before.maximum != pool.maximum:
            raise ValueError(
                f"cannot refill {pool.ref.index!r} resource {before} to {pool.maximum}"
            )
        resources[key] = updated(before, remaining=pool.maximum)
    return _with_resources(state, resources)


def apply(state: GameState, events: Sequence[Event]) -> GameState:
    return reduce(_apply_one, events, state)


def render(events: Sequence[Event]) -> str:
    """Render the only mechanical evidence shown to the Narrator."""
    return "\n".join(f"- {e.summary}" for e in events) or "- (nothing mechanical happened)"
