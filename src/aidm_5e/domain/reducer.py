from collections.abc import Mapping, Sequence
from functools import reduce

from aidm.domain.base import PLAYER_ID, EntityId
from aidm.domain.entities import ActorEntity
from aidm.domain.events import (
    ActorMoved,
    EntityCreated,
    EntityDiscovered,
    ItemMoved,
)
from aidm.domain.reducer import apply_core
from aidm.domain.state import GameState
from aidm.utils.models import updated

from ..content.records.base import ContentRef
from ..models import Dnd5eActorState, Dnd5eState
from ..state import created_state, dnd5e_state
from .models.events import (
    AttackRolled,
    ConditionChanged,
    DcRolled,
    DiceRolled,
    Dnd5eEvent,
    Dnd5eRuleEvent,
    FeatureActivated,
    FeatureUsed,
    HpChanged,
    LeveledUp,
    LevelUpAvailable,
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


def apply_rule(state: GameState, event: Dnd5eRuleEvent) -> Dnd5eState:
    engine = dnd5e_state(state)
    match event:
        case DcRolled() | DiceRolled() | AttackRolled() | FeatureActivated() | SpellCast():
            return engine  # branches carry effects; rolls are evidence
        case HpChanged(target_id=target_id, delta=delta):
            actor = _actor(state, engine, target_id)
            stats = actor.stats.with_hp_delta(delta)
            return engine.with_actor(target_id, updated(actor, stats=stats))
        case ConditionChanged(target_id=target_id, condition=condition, active=active):
            actor = _actor(state, engine, target_id)
            stats = actor.stats.with_condition(condition, active=active)
            return engine.with_actor(target_id, updated(actor, stats=stats))
        case LevelUpAvailable():
            return _with_progression(engine, updated(_progression(engine), level_up_available=True))
        case FeatureUsed(ref=ref, spent=spent, remaining=remaining, maximum=maximum):
            return _spent(engine, ref, spent=spent, remaining=remaining, maximum=maximum)
        case SpellSlotSpent(slot_level=level, remaining=remaining, maximum=maximum):
            return _slot_spent(engine, level, remaining=remaining, maximum=maximum)
        case Rested(refilled=refilled, slots=slots):
            return _refilled(engine, refilled, slots)
        case LeveledUp(advancement=advancement):
            return _grown(engine, advancement)


def apply(state: GameState, events: Sequence[Dnd5eEvent]) -> GameState:
    """Fold a resolution's own events so a later mechanic reads what an earlier one produced."""
    return reduce(_apply_one, events, state)


def _apply_one(state: GameState, event: Dnd5eEvent) -> GameState:
    match event:
        case EntityCreated() | EntityDiscovered() | ActorMoved() | ItemMoved():
            return apply_core(state, event, created_state)
        case _:
            return updated(state, engine=apply_rule(state, event))


def _actor(state: GameState, engine: Dnd5eState, actor_id: EntityId) -> Dnd5eActorState:
    state.world.require_kind(actor_id, ActorEntity)
    return engine.actor(actor_id)


def _grown(engine: Dnd5eState, advancement: Advancement) -> Dnd5eState:
    """Require the next level because applying an HP gain twice is not idempotent."""
    player = engine.actor(PLAYER_ID)
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
    return engine.with_actor(
        PLAYER_ID, updated(player, stats=stats, progression=advancement.progression)
    )


def _progression(engine: Dnd5eState) -> Progression:
    progression = engine.actor(PLAYER_ID).progression
    if progression is None:
        raise ValueError("the player has no feature resources")
    return progression


def _with_progression(engine: Dnd5eState, progression: Progression) -> Dnd5eState:
    player = engine.actor(PLAYER_ID)
    return engine.with_actor(PLAYER_ID, updated(player, progression=progression))


def _with_pools(
    engine: Dnd5eState,
    feature_resources: Mapping[FeatureKey, ResourceState],
    spell_slots: Mapping[int, ResourceState],
) -> Dnd5eState:
    progression = updated(
        _progression(engine), feature_resources=feature_resources, spell_slots=spell_slots
    )
    return _with_progression(engine, progression)


def _spent(
    engine: Dnd5eState, ref: ContentRef, *, spent: int, remaining: int, maximum: int
) -> Dnd5eState:
    key = feature_key(ref)
    progression = _progression(engine)
    held = progression.feature_resources
    before = held.get(key)
    if before is None or maximum != before.maximum or remaining != before.remaining - spent:
        raise ValueError(
            f"cannot spend {spent} from {ref.index!r} resource {before} to {remaining}/{maximum}"
        )
    return _with_pools(
        engine, {**held, key: updated(before, remaining=remaining)}, progression.spell_slots
    )


def _slot_spent(engine: Dnd5eState, level: int, *, remaining: int, maximum: int) -> Dnd5eState:
    progression = _progression(engine)
    held = progression.spell_slots
    before = held.get(level)
    if before is None or maximum != before.maximum or remaining != before.remaining - 1:
        raise ValueError(
            f"cannot spend a level {level} spell slot {before} to {remaining}/{maximum}"
        )
    return _with_pools(
        engine,
        progression.feature_resources,
        {**held, level: updated(before, remaining=remaining)},
    )


def _refilled(
    engine: Dnd5eState, refilled: Sequence[PoolRefilled], slots: Sequence[SlotsRefilled]
) -> Dnd5eState:
    progression = _progression(engine)
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
    return _with_pools(engine, resources, spell_slots)


def _full(before: ResourceState | None, maximum: int, what: str) -> ResourceState:
    if before is None or before.maximum != maximum:
        raise ValueError(f"cannot refill {what} {before} to {maximum}")
    return updated(before, remaining=maximum)
