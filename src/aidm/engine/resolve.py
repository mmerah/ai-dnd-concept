"""Director plan -> events. Pure: no LLM, no I/O; takes the `Plan` only, so `engine/` stays blind
to intent/tone/speaker."""

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
    GainCanonItem,
    GainLooseItem,
    GameState,
    LoseCanonItem,
    LoseLooseItem,
    ModifyHp,
    Move,
    Plan,
    find,
)
from . import rules


def resolve(plan: Plan, state: GameState, rng: Random) -> list[Event]:
    events: list[Event] = []
    passed = True
    if plan.check is not None:
        rolled = rules.roll_check(state.character, plan.check.ability, plan.check.dc, rng)
        events.append(rolled)
        passed = rolled.success
    branch = plan.on_success if passed else plan.on_failure
    # Fold over the draft-so-far so each consequence sees prior ones — a second reveal of the same
    # entity then correctly no-ops, exactly as the deleted Actor's apply-so-far draft did.
    draft = state
    for consequence in [*plan.unconditional, *branch]:
        new = _events_for(consequence, draft)
        events.extend(new)
        draft = apply(draft, new)
    return events


def _entity(state: GameState, entity_id: EntityId) -> Entity:
    entity = find(state.world.entities, entity_id)
    if entity is None:  # backstop; the Director's output validator catches this first as a retry
        raise ValueError(f"plan referenced unknown entity id {entity_id!r}")
    return entity


def _events_for(consequence: Consequence, state: GameState) -> list[Event]:
    """Canon items canonicalize to `entity.name`; a hidden canon gain reveals the entity first.
    Loose items are stored verbatim with no canon entity."""
    match consequence:
        case Discover(entity_id=entity_id):
            entity = _entity(state, entity_id)
            if entity.known:  # discovering an already-known entity is a no-op, not an error
                return []
            return [EntityDiscovered(entity_id=entity.id, name=entity.name)]
        case GainCanonItem(entity_id=entity_id):
            entity = _entity(state, entity_id)
            events: list[Event] = []
            if not entity.known:  # taking a thing is learning of it
                events.append(EntityDiscovered(entity_id=entity.id, name=entity.name))
            events.append(InventoryChanged(item=entity.name, delta=1))
            return events
        case GainLooseItem(item=item):
            return [InventoryChanged(item=item, delta=1)]
        case LoseCanonItem(entity_id=entity_id):
            return [InventoryChanged(item=_entity(state, entity_id).name, delta=-1)]
        case LoseLooseItem(item=item):  # reducer fails the turn whole if the string is not held
            return [InventoryChanged(item=item, delta=-1)]
        case ModifyHp(delta=delta):
            return [HpChanged(delta=delta)]
        case Move(location=location):
            return [Moved(location=location)]
