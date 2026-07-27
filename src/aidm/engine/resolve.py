"""Director mechanics -> events. Pure: no LLM, no I/O; takes the consequence list only, so
`engine/` stays blind to intent/tone/speaker. Consequences are a recursive tree: `roll_check`
folds the selected branch. Guards here fail fast on a broken plan; the Director's validator
catches most first as a retry."""

from collections.abc import Sequence
from random import Random
from typing import Literal

from ..content import Library
from ..content.vocabulary import ConditionName
from ..domain.models import (
    ActorEntity,
    ApplyCondition,
    Attack,
    ConditionChanged,
    Consequence,
    Damage,
    DcRoll,
    DcRolled,
    Discover,
    DropItem,
    Entity,
    EntityCreated,
    EntityDiscovered,
    EntityId,
    Event,
    GainImprovisedItem,
    GameState,
    GiveItem,
    Heal,
    HpChanged,
    ItemDestination,
    ItemEntity,
    ItemMoved,
    LocationEntity,
    Magnitude,
    Move,
    Moved,
    RollCheck,
    RollSave,
    TakeItem,
    find,
)
from ..domain.reducer import apply
from ..utils import dice
from ..utils.ids import slug
from . import procedures, rules


def resolve(
    mechanics: Sequence[Consequence], state: GameState, rng: Random, library: Library
) -> list[Event]:
    """Fold left to right, so each consequence sees the state its predecessors produced."""
    events: list[Event] = []
    for consequence in mechanics:
        new = _walk(consequence, state, rng, library)
        events.extend(new)
        state = apply(state, new)
    return events


def _walk(consequence: Consequence, draft: GameState, rng: Random, library: Library) -> list[Event]:
    """Canon references canonicalize to `entity.name`, revealing an entity as it enters the player's
    view. An improvised item is promoted to a canon item so an inventory holds a real id."""
    player = draft.player
    match consequence:
        case RollCheck(ability=ability, dc=dc):
            rolled = rules.roll_check(player, ability, dc, rng)
            return _branched((), rolled, consequence, draft, rng, library)
        case RollSave(ability=ability, dc=dc, target_id=target_id):
            target = _target(draft, target_id)
            rolled = rules.roll_save(target, ability, dc, rng)
            return _branched(_reveal(target), rolled, consequence, draft, rng, library)
        case Attack(weapon=weapon, target_id=target_id, attacker_id=attacker_id):
            attacker, target = _target(draft, attacker_id), _target(draft, target_id)
            return _attack_events(draft, attacker, target, weapon, rng, library)
        case Damage(amount=amount, target_id=target_id):
            return _hp_events(draft, target_id, amount, rng, sign=-1)
        case Heal(amount=amount, target_id=target_id):
            return _hp_events(draft, target_id, amount, rng, sign=+1)
        case ApplyCondition(condition=condition, ends=ends, target_id=target_id):
            return _condition_events(draft, target_id, condition, active=not ends)
        case Discover(entity_id=entity_id):
            return _reveal(_entity(draft, entity_id))  # re-discovery is a no-op, not an error
        case Move(location_id=location_id, actor_id=actor_id):
            return _move(draft, location_id, actor_id)
        case TakeItem(item_id=item_id):
            item = _item(draft, item_id)
            if item.location_id != player.location_id:
                raise ValueError(f"cannot take {item_id!r}: it is not at the player's location")
            return [*_reveal(item), _item_moved(item, player.id, player.name, "actor")]
        case DropItem(item_id=item_id):
            item = _held(draft, item_id, "drop")
            here = _location(draft, player.location_id)
            return [_item_moved(item, here.id, here.name, "location")]
        case GiveItem(item_id=item_id, actor_id=actor_id):
            item = _held(draft, item_id, "give")
            if actor_id == player.id:
                raise ValueError("cannot give an item to the player: they already hold it")
            actor = _actor_here(draft, actor_id)
            return [_item_moved(item, actor.id, actor.name, "actor")]
        case GainImprovisedItem(item_name=item_name):
            item = ItemEntity(
                id=slug(item_name, draft.world.entities.keys()),
                name=item_name,
                brief=item_name,  # improvised: the brief is just the written-out name
                location_id=player.location_id,  # created lying here, then picked up
                known=True,
                authored=False,
            )
            took = _item_moved(item, player.id, player.name, "actor")
            return [EntityCreated(entity=item), took]


def _branched(
    before: Sequence[Event],
    rolled: DcRolled,
    consequence: DcRoll,
    draft: GameState,
    rng: Random,
    library: Library,
) -> list[Event]:
    """The roll and whatever preceded it, then only the branch the roll selected. The branch folds
    against the state *all* of them produced, so a reveal already emitted is not emitted twice."""
    emitted = [*before, rolled]
    branch = consequence.on_success if rolled.success else consequence.on_failure
    return [*emitted, *resolve(branch, apply(draft, emitted), rng, library)]


def _attack_events(
    draft: GameState,
    attacker: ActorEntity,
    target: ActorEntity,
    weapon: str,
    rng: Random,
    library: Library,
) -> list[Event]:
    """A miss is still evidence, so the roll is emitted either way; the damage reuses the same hp
    path as `damage`, so the clamp and the zero-delta rule cannot diverge from it."""
    if attacker.id == target.id:
        raise ValueError(f"cannot attack {target.id!r}: an actor does not strike at themselves")
    swung = procedures.swing(draft, attacker, weapon, library)
    rolled = procedures.strike(attacker, target, swung, rng)
    seen: list[Event] = [*_reveal(attacker), *_reveal(target), rolled]
    if not rolled.hit or swung.damage is None:
        return seen
    return [*seen, *_hp_events(apply(draft, seen), target.id, swung.damage, rng, sign=-1)]


def _move(draft: GameState, location_id: EntityId, actor_id: EntityId | None) -> list[Event]:
    """Another actor's move must touch the player's location, so the summary never narrates
    movement the player could not witness; arriving where the player is also reveals them."""
    dest = _location(draft, location_id)
    player = draft.player
    if actor_id is None or actor_id == player.id:  # arriving somewhere hidden reveals it
        return [*_reveal(dest), _moved(player, dest)]
    actor = _actor(draft, actor_id)
    if actor.location_id != player.location_id and dest.id != player.location_id:
        raise ValueError(f"cannot move {actor_id!r}: the player would not witness it")
    reveal = _reveal(actor) if dest.id == player.location_id else []
    return [*reveal, _moved(actor, dest)]


def _moved(actor: ActorEntity, dest: LocationEntity) -> Moved:
    return Moved(
        actor_id=actor.id, actor_name=actor.name, location_id=dest.id, location_name=dest.name
    )


def _magnitude(amount: Magnitude, rng: Random) -> tuple[int, list[Event]]:
    """The roll is folded into the change that spends it: dice fall here, so the Narrator gets the
    die as evidence with no value flowing between consequences. A constant carries no die however
    it is written, so `4` and `'4'` reach the Narrator identically."""
    if isinstance(amount, int):
        return amount, []
    total, rolled = rules.roll_dice(amount, rng)
    return total, [] if dice.is_constant(amount) else [rolled]


def _hp_events(
    draft: GameState,
    target_id: EntityId | None,
    amount: Magnitude,
    rng: Random,
    *,
    sign: Literal[1, -1],
) -> list[Event]:
    """Harming or healing someone unseen reveals them, since the events name them."""
    target = _target(draft, target_id)
    total, rolls = _magnitude(amount, rng)
    changed = _hp_changed(target, sign * total)
    # A change the clamp swallows whole is not an event: no hit point moved, so none is reported.
    events: list[Event] = [*_reveal(target), *rolls]
    return events if changed.delta == 0 else [*events, changed]


def _condition_events(
    draft: GameState,
    target_id: EntityId | None,
    condition: ConditionName,
    *,
    active: bool,
) -> list[Event]:
    """Immunity and redundancy are absorbed, not narrated: a devil the poison never touched, or a
    second helping of `prone`, changed nothing and so is not an event. `with_condition` is asked
    rather than re-implemented, so the rule cannot drift from the one the reducer applies. The
    reveal still happens, because the Director acted on someone the player must have seen."""
    target = _target(draft, target_id)
    if target.stats.with_condition(condition, active=active) == target.stats:
        return _reveal(target)
    changed = ConditionChanged(
        target_id=target.id, target_name=target.name, condition=condition, active=active
    )
    return [*_reveal(target), changed]


def _hp_changed(actor: ActorEntity, delta: int) -> HpChanged:
    """`delta` is what the clamp will actually apply, so the Narrator is never told of hit points
    that never moved: `with_hp_delta` stays the one clamp, here as much as in the reducer."""
    after = actor.stats.with_hp_delta(delta)
    return HpChanged(
        target_id=actor.id,
        target_name=actor.name,
        delta=after.hp - actor.stats.hp,
        wounds=after.wounds,
    )


def _item_moved(item: Entity, to_id: EntityId, to_name: str, to_kind: ItemDestination) -> ItemMoved:
    return ItemMoved(
        item_id=item.id, item_name=item.name, to_id=to_id, to_name=to_name, to_kind=to_kind
    )


def _entity(state: GameState, entity_id: EntityId) -> Entity:
    entity = find(state.world.entities, entity_id)
    if entity is None:
        raise ValueError(f"mechanics referenced unknown entity id {entity_id!r}")
    return entity


def _location(state: GameState, entity_id: EntityId) -> LocationEntity:
    entity = _entity(state, entity_id)
    if not isinstance(entity, LocationEntity):
        raise ValueError(f"mechanics used {entity_id!r} as a location, but it is a {entity.kind}")
    return entity


def _actor(state: GameState, entity_id: EntityId) -> ActorEntity:
    entity = _entity(state, entity_id)
    if not isinstance(entity, ActorEntity):
        raise ValueError(f"mechanics used {entity_id!r} as an actor, but it is a {entity.kind}")
    return entity


def _actor_here(state: GameState, entity_id: EntityId) -> ActorEntity:
    """An actor the player is standing with; anyone else is off-screen, and what the player never
    witnessed must not reach the Narrator."""
    actor = _actor(state, entity_id)
    if actor.location_id != state.player.location_id:
        raise ValueError(f"cannot affect {entity_id!r}: not at the player's location")
    return actor


def _target(state: GameState, entity_id: EntityId | None) -> ActorEntity:
    """An omitted actor id is the player throughout the vocabulary — they are the one actor no role
    is shown an id for."""
    return state.player if entity_id is None else _actor_here(state, entity_id)


def _item(state: GameState, entity_id: EntityId) -> ItemEntity:
    entity = _entity(state, entity_id)
    if not isinstance(entity, ItemEntity):
        raise ValueError(f"mechanics used {entity_id!r} as an item, but it is a {entity.kind}")
    return entity


def _held(state: GameState, entity_id: EntityId, verb: str) -> ItemEntity:
    item = _item(state, entity_id)
    if entity_id not in state.player.inventory:
        raise ValueError(f"cannot {verb} {entity_id!r}: the player is not carrying it")
    return item


def _reveal(entity: Entity) -> list[Event]:
    """Reaching or taking a hidden thing is learning of it."""
    return [] if entity.known else [EntityDiscovered(entity_id=entity.id, name=entity.name)]
