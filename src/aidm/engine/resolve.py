"""Director mechanics -> events. Pure: no LLM, no I/O; takes the `Mechanics` only, so `engine/`
stays blind to intent/tone/speaker."""

from random import Random

from ..domain.events import (
    EntityDiscovered,
    Event,
    HpChanged,
    InventoryChanged,
    Moved,
    apply,
)
from ..domain.models import (
    Consequence,
    Discover,
    Entity,
    EntityId,
    GainImprovisedItem,
    GainItem,
    GameState,
    Kind,
    LoseImprovisedItem,
    LoseItem,
    Mechanics,
    ModifyHp,
    Move,
    find,
)
from . import rules


def resolve(mechanics: Mechanics, state: GameState, rng: Random) -> list[Event]:
    events: list[Event] = []
    passed = True
    if mechanics.check is not None:
        rolled = rules.roll_check(state.character, mechanics.check.ability, mechanics.check.dc, rng)
        events.append(rolled)
        passed = rolled.success
    branch = mechanics.on_success if passed else mechanics.on_failure
    # Fold over the draft-so-far so each consequence sees prior ones — a second reveal of the same
    # entity then correctly no-ops, exactly as the deleted Actor's apply-so-far draft did.
    draft = state
    for consequence in [*mechanics.unconditional, *branch]:
        new = _events_for(consequence, draft)
        events.extend(new)
        draft = apply(draft, new)
    return events


def _entity(state: GameState, entity_id: EntityId, kind: Kind | None = None) -> Entity:
    """Backstop; the Director's output validator catches both faults first, as a retry. `kind` is
    None only for `discover`, which may reveal anything."""
    entity = find(state.world.entities, entity_id)
    if entity is None:
        raise ValueError(f"mechanics referenced unknown entity id {entity_id!r}")
    if kind is not None and entity.kind != kind:
        raise ValueError(f"mechanics used {entity_id!r} as a {kind}, but it is a {entity.kind}")
    return entity


def _reveal(entity: Entity) -> list[Event]:
    """Reaching or taking a hidden thing is learning of it."""
    return [] if entity.known else [EntityDiscovered(entity_id=entity.id, name=entity.name)]


def _events_for(consequence: Consequence, state: GameState) -> list[Event]:
    """Canon references canonicalize to `entity.name`, revealing the entity first if it was hidden.
    Improvised items are stored verbatim with no canon entity."""
    match consequence:
        case Discover(entity_id=entity_id):
            return _reveal(_entity(state, entity_id))  # re-discovery is a no-op, not an error
        case GainItem(item_id=item_id):
            entity = _entity(state, item_id, "item")
            return [*_reveal(entity), InventoryChanged(item=entity.name, delta=1)]
        case GainImprovisedItem(item_name=item_name):
            return [InventoryChanged(item=item_name, delta=1)]
        case LoseItem(item_id=item_id):
            return [InventoryChanged(item=_entity(state, item_id, "item").name, delta=-1)]
        case LoseImprovisedItem(item_name=item_name):  # reducer fails the turn if not held
            return [InventoryChanged(item=item_name, delta=-1)]
        case ModifyHp(delta=delta):
            return [HpChanged(delta=delta)]
        case Move(location_id=location_id):
            entity = _entity(state, location_id, "location")
            return [*_reveal(entity), Moved(entity_id=entity.id, name=entity.name)]
