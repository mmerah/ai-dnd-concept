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
    SlotsRefilled,
    SpellCast,
    SpellSlotSpent,
)
from .models.progression import (
    Advancement,
    FeatureKey,
    Progression,
    ResourceState,
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
        case DcRolled() | DiceRolled() | AttackRolled() | FeatureActivated() | SpellCast():
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
        case SpellSlotSpent(slot_level=level, remaining=remaining, maximum=maximum):
            return _slot_spent(state, level, remaining=remaining, maximum=maximum)
        case Rested(refilled=refilled, slots=slots):
            return _refilled(state, refilled, slots)
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


def _with_pools(
    state: GameState,
    feature_resources: Mapping[FeatureKey, ResourceState],
    spell_slots: Mapping[int, ResourceState],
) -> GameState:
    progression = updated(
        _progression(state), feature_resources=feature_resources, spell_slots=spell_slots
    )
    return _replacing(state, updated(state.player, progression=progression))


def _spent(
    state: GameState, ref: ContentRef, *, spent: int, remaining: int, maximum: int
) -> GameState:
    key = feature_key(ref)
    progression = _progression(state)
    held = progression.feature_resources
    before = held.get(key)
    if before is None or maximum != before.maximum or remaining != before.remaining - spent:
        raise ValueError(
            f"cannot spend {spent} from {ref.index!r} resource {before} to {remaining}/{maximum}"
        )
    return _with_pools(
        state, {**held, key: updated(before, remaining=remaining)}, progression.spell_slots
    )


def _slot_spent(state: GameState, level: int, *, remaining: int, maximum: int) -> GameState:
    progression = _progression(state)
    held = progression.spell_slots
    before = held.get(level)
    if before is None or maximum != before.maximum or remaining != before.remaining - 1:
        raise ValueError(
            f"cannot spend a level {level} spell slot {before} to {remaining}/{maximum}"
        )
    return _with_pools(
        state,
        progression.feature_resources,
        {**held, level: updated(before, remaining=remaining)},
    )


def _refilled(
    state: GameState, refilled: Sequence[PoolRefilled], slots: Sequence[SlotsRefilled]
) -> GameState:
    progression = _progression(state)
    resources = dict(progression.feature_resources)
    for pool in refilled:
        key = feature_key(pool.ref)
        resources[key] = _full(resources.get(key), pool.maximum, f"{pool.ref.index!r} resource")
    spell_slots = dict(progression.spell_slots)
    for slot in slots:
        level = slot.slot_level
        spell_slots[level] = _full(
            spell_slots.get(level), slot.maximum, f"level {level} spell slots"
        )
    return _with_pools(state, resources, spell_slots)


def _full(before: ResourceState | None, maximum: int, what: str) -> ResourceState:
    if before is None or before.maximum != maximum:
        raise ValueError(f"cannot refill {what} {before} to {maximum}")
    return updated(before, remaining=maximum)


def apply(state: GameState, events: Sequence[Event]) -> GameState:
    return reduce(_apply_one, events, state)
