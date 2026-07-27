"""Director mechanics -> events. Pure: no LLM, no I/O; takes the consequence list only, so
`engine/` stays blind to intent/tone/speaker. Consequences are a recursive tree: `roll_check`
folds the selected branch, `roll_dice` binds a total later consequences reference. Guards here
fail fast on a broken plan; the Director's validator catches most first as a retry."""

from collections.abc import Sequence
from random import Random

from ..domain.models import (
    ActorEntity,
    Amount,
    Consequence,
    Damage,
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
    Move,
    Moved,
    Ref,
    RollCheck,
    RollDice,
    TakeItem,
    find,
    make_entity,
)
from ..domain.reducer import apply
from ..utils.ids import slug
from . import rules


def resolve(mechanics: Sequence[Consequence], state: GameState, rng: Random) -> list[Event]:
    events, _ = _apply_seq(mechanics, state, rng, {})
    return events


def _apply_seq(
    consequences: Sequence[Consequence], draft: GameState, rng: Random, bindings: dict[str, int]
) -> tuple[list[Event], GameState]:
    """Fold left to right. `scope` is this sequence's own copy: a `roll_dice` bind reaches later
    siblings but never escapes to an enclosing sequence or the other branch of a check — so a
    leaked cross-branch ref hard-fails here rather than reading a stale value."""
    scope = dict(bindings)
    events: list[Event] = []
    for consequence in consequences:
        new = _walk(consequence, draft, rng, scope)
        events.extend(new)
        draft = apply(draft, new)
    return events, draft


def _walk(
    consequence: Consequence, draft: GameState, rng: Random, bindings: dict[str, int]
) -> list[Event]:
    """Canon references canonicalize to `entity.name`, revealing an entity as it enters the player's
    view. An improvised item is promoted to a canon item so an inventory holds a real id."""
    player = draft.player
    match consequence:
        case RollCheck(ability=ability, dc=dc, on_success=on_success, on_failure=on_failure):
            rolled = rules.roll_check(player, ability, dc, rng)
            branch = on_success if rolled.success else on_failure
            sub, _ = _apply_seq(branch, apply(draft, [rolled]), rng, bindings)
            return [rolled, *sub]
        case RollDice(dice=dice, bind=bind, then=then):
            total, event = rules.roll_dice(dice, rng)
            bindings[bind] = total
            sub, _ = _apply_seq(then, apply(draft, [event]), rng, bindings)
            return [event, *sub]
        case Damage(amount=amount):
            return [_hp_changed(player, -_value(amount, bindings))]
        case Heal(amount=amount):
            return [_hp_changed(player, +_value(amount, bindings))]
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
            actor = _actor(draft, actor_id)
            if actor.id == player.id:
                raise ValueError("cannot give an item to the player: they already hold it")
            if actor.location_id != player.location_id:
                raise ValueError(f"cannot give to {actor_id!r}: not at the player's location")
            return [_item_moved(item, actor.id, actor.name, "actor")]
        case GainImprovisedItem(item_name=item_name):
            item = make_entity(
                "item",
                id=slug(item_name, draft.world.entities.keys()),
                name=item_name,
                brief=item_name,  # improvised: the brief is just the written-out name
                location_id=player.location_id,  # created lying here, then picked up
                known=True,
                authored=False,
            )
            took = _item_moved(item, player.id, player.name, "actor")
            return [EntityCreated(entity=item), took]


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


def _hp_changed(actor: ActorEntity, delta: int) -> HpChanged:
    return HpChanged(
        target_id=actor.id,
        target_name=actor.name,
        delta=delta,
        condition=actor.stats.with_hp_delta(delta).condition,
    )


def _item_moved(item: Entity, to_id: EntityId, to_name: str, to_kind: ItemDestination) -> ItemMoved:
    return ItemMoved(
        item_id=item.id, item_name=item.name, to_id=to_id, to_name=to_name, to_kind=to_kind
    )


def _value(amount: Amount, bindings: dict[str, int]) -> int:
    if isinstance(amount, Ref):
        if amount.ref not in bindings:  # the Director validator catches a dangling ref first
            raise ValueError(f"reference {amount.ref!r} was never rolled this turn")
        return bindings[amount.ref]
    return amount


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
