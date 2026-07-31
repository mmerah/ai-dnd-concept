from collections.abc import Callable, Sequence
from typing import Protocol

from ..utils.models import updated
from .base import EntityId
from .engine import require_engine
from .entities import ActorEntity, Entity, ItemEntity, LocationEntity
from .events import (
    ActorMoved,
    CoreEvent,
    EntityCreated,
    EntityDiscovered,
    Event,
    ItemMoved,
    RuleEvent,
    RuleStatePatch,
)
from .presentation import narrator_core_event
from .state import GameState, WorldState


class RuleReducer(Protocol):
    def apply(self, state: GameState, event: RuleEvent) -> RuleStatePatch: ...
    def validate_state(self, state: GameState) -> None: ...


def _replace(state: GameState, entity: Entity) -> GameState:
    return updated(state, world=state.world.replacing(entity))


def _apply_core(state: GameState, event: CoreEvent) -> GameState:
    world = state.world
    match event:
        case EntityCreated(entity=entity):
            if entity.rules is not None:
                require_engine(entity.rules, state.engine, f"created entity {entity.id!r} rules")
            return updated(state, world=world.adding(entity))
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


def _apply_patch(state: GameState, patch: RuleStatePatch) -> GameState:
    unknown = sorted(set(patch.entity_rules) - set(state.world.entities))
    if unknown:
        raise ValueError(f"rule patch names unknown entity ids: {unknown}")
    game_rules = state.rules if patch.game_rules is None else patch.game_rules
    require_engine(game_rules, state.engine, "patched game rules")
    entities: dict[EntityId, Entity] = dict(state.world.entities)
    for entity_id, rules in patch.entity_rules.items():
        if rules is not None:
            require_engine(rules, state.engine, f"patched entity {entity_id!r} rules")
        entities[entity_id] = updated(entities[entity_id], rules=rules)
    return updated(state, rules=game_rules, world=WorldState(entities=entities))


def apply_one(state: GameState, event: Event, rules: RuleReducer) -> GameState:
    if isinstance(event, RuleEvent):
        if event.engine != state.engine:
            raise ValueError(
                f"rule event engine is {event.engine!r}, state engine is {state.engine!r}"
            )
        next_state = _apply_patch(state, rules.apply(state, event))
    else:
        next_state = _apply_core(state, event)
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
