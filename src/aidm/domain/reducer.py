from collections.abc import Callable, Sequence
from typing import Protocol

from ..utils.models import updated
from .entities import ActorEntity, Entity, ItemEntity, LocationEntity
from .events import (
    ActorMoved,
    CoreEvent,
    EntityCreated,
    EntityDiscovered,
    Event,
    ItemMoved,
    RuleEvent,
)
from .presentation import narrator_core_event
from .state import EngineState, GameState

type CreatedEngineState = Callable[[GameState, Entity], EngineState]


class RuleReducer(Protocol):
    def apply(self, state: GameState, event: RuleEvent) -> EngineState: ...
    def created(self, state: GameState, entity: Entity) -> EngineState: ...
    def validate_state(self, state: GameState) -> None: ...


def _replace(state: GameState, entity: Entity) -> GameState:
    return updated(state, world=state.world.replacing(entity))


def apply_core(state: GameState, event: CoreEvent, created: CreatedEngineState) -> GameState:
    """Core owns topology, so engines fold their own core events through this too."""
    world = state.world
    match event:
        case EntityCreated(entity=entity):
            return updated(
                state,
                world=world.adding(entity),
                engine=created(state, entity),
            )
        case EntityDiscovered(entity_id=entity_id):
            return _replace(state, updated(world.require(entity_id), known=True))
        case ActorMoved(actor_id=actor_id, location_id=location_id):
            world.require_kind(location_id, LocationEntity)
            actor = world.require_kind(actor_id, ActorEntity)
            return _replace(state, updated(actor, location_id=location_id))
        case ItemMoved(item_id=item_id, to_id=to_id):
            item = world.require_kind(item_id, ItemEntity)
            if not isinstance(world.require(to_id), ActorEntity | LocationEntity):
                raise ValueError(f"cannot move {item_id!r} to {to_id!r}")
            return _replace(state, updated(item, container_id=to_id))


def apply_one(state: GameState, event: Event, rules: RuleReducer) -> GameState:
    if isinstance(event, RuleEvent):
        if event.engine != state.engine_id:
            raise ValueError(
                f"rule event engine is {event.engine!r}, state engine is {state.engine_id!r}"
            )
        next_state = updated(state, engine=rules.apply(state, event))
    else:
        next_state = apply_core(state, event, rules.created)
    rules.validate_state(next_state)
    return next_state


def apply(state: GameState, events: Sequence[Event], rules: RuleReducer) -> GameState:
    result = state
    for event in events:
        result = apply_one(result, event, rules)
    return result


def narrator_evidence(
    events: Sequence[Event],
    render_rule: Callable[[RuleEvent], str | None],
) -> str:
    lines: list[str] = []
    for event in events:
        rendered = (
            render_rule(event) if isinstance(event, RuleEvent) else narrator_core_event(event)
        )
        if rendered is not None:
            lines.append(f"- {rendered}")
    return "\n".join(lines) or "- (nothing mechanical happened)"
