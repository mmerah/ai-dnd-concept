"""Typed events and the single pure reducer. Nothing else in the app produces state."""

from collections.abc import Sequence
from functools import reduce
from typing import Annotated, Literal

from pydantic import Field

from .models import Ability, Entity, EntityId, Frozen, GameState, find, updated


class CheckRolled(Frozen):
    type: Literal["check_rolled"] = "check_rolled"
    ability: Ability
    dc: int
    roll: int
    total: int
    success: bool

    @property
    def summary(self) -> str:
        verdict = "SUCCESS" if self.success else "FAILURE"
        return f"{self.ability} check: {self.roll} -> {self.total} vs DC {self.dc}: {verdict}"


class InventoryChanged(Frozen):
    type: Literal["inventory_changed"] = "inventory_changed"
    item: str
    delta: Literal[1, -1]

    @property
    def summary(self) -> str:
        return f"{'gained' if self.delta > 0 else 'lost'} item: {self.item}"


class HpChanged(Frozen):
    type: Literal["hp_changed"] = "hp_changed"
    delta: int

    @property
    def summary(self) -> str:
        return f"hp {self.delta:+d}"


class Moved(Frozen):
    type: Literal["moved"] = "moved"
    location: str

    @property
    def summary(self) -> str:
        return f"moved to {self.location}"


class EntityDiscovered(Frozen):
    type: Literal["entity_discovered"] = "entity_discovered"
    entity_id: EntityId
    name: str

    @property
    def summary(self) -> str:
        return f"learned of {self.name}"


class EntityCreated(Frozen):
    type: Literal["entity_created"] = "entity_created"
    entity: Entity

    @property
    def summary(self) -> str:
        return f"new {self.entity.kind}: {self.entity.name}"


Event = Annotated[
    CheckRolled | InventoryChanged | HpChanged | Moved | EntityDiscovered | EntityCreated,
    Field(discriminator="type"),
]


def _with_entities(state: GameState, entities: list[Entity]) -> GameState:
    return updated(state, world=updated(state.world, entities=entities))


def _apply_one(state: GameState, event: Event) -> GameState:
    match event:
        case CheckRolled():  # evidence for the Narrator; the consequences are separate events
            return state
        case InventoryChanged(item=item, delta=delta):
            inventory = list(state.character.inventory)
            if delta > 0:
                inventory.append(item)
            elif item in inventory:
                inventory.remove(item)
            else:
                raise ValueError(f"cannot lose {item!r}: not in inventory")
            return updated(state, character=updated(state.character, inventory=inventory))
        case HpChanged(delta=delta):
            hp = max(0, min(state.character.max_hp, state.character.hp + delta))
            return updated(state, character=updated(state.character, hp=hp))
        case Moved(location=location):
            return updated(state, character=updated(state.character, location=location))
        case EntityDiscovered(entity_id=entity_id):
            if find(state.world.entities, entity_id) is None:
                raise ValueError(f"cannot discover unknown entity {entity_id!r}")
            entities = [
                updated(e, known=True) if e.id == entity_id else e for e in state.world.entities
            ]
            return _with_entities(state, entities)
        case EntityCreated(entity=entity):
            return _with_entities(state, [*state.world.entities, entity])


def apply(state: GameState, events: Sequence[Event]) -> GameState:
    """Pure: never mutates `state`."""
    return reduce(_apply_one, events, state)


def render(events: Sequence[Event]) -> str:
    """Player-visible event summaries — the Narrator's only source of truth."""
    return "\n".join(f"- {e.summary}" for e in events) or "- (nothing mechanical happened)"
