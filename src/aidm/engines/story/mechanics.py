from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field

from aidm.content.authored import Rules
from aidm.engines.counters import (
    Counter,
    CounterChange,
    adjust,
    render_counters,
    spend,
    write_mechanics,
)
from aidm.engines.loader import EntityRenderer
from aidm.state.apply import apply_effect, reveal_target
from aidm.state.base import PLAYER_ID, Entity, EntityId, Mutable, Slug
from aidm.state.effects import WorldOp
from aidm.state.facts import Fact
from aidm.state.world import GameState

type Approach = Literal["bold", "subtle", "clever", "empathetic"]
APPROACHES: tuple[Approach, ...] = ("bold", "subtle", "clever", "empathetic")

type StoryEffect = Annotated[WorldOp | CounterChange, Field(discriminator="op")]


class Adventurer(Mutable):
    bold: int = 0
    subtle: int = 0
    clever: int = 0
    empathetic: int = 0
    stress: Counter = Counter(current=0, maximum=5)
    growth: Counter = Counter(current=0, maximum=3)

    def approach(self, name: Approach) -> int:
        return self.approaches()[name]

    def approaches(self) -> dict[Approach, int]:
        return {
            "bold": self.bold,
            "subtle": self.subtle,
            "clever": self.clever,
            "empathetic": self.empathetic,
        }

    def raise_approach(self, name: Approach) -> int:
        raised = self.approach(name) + 1
        setattr(self, name, raised)
        return raised

    def counters(self) -> dict[Slug, Counter]:
        return {"growth": self.growth, "stress": self.stress}


class Mechanics(Mutable):
    actors: dict[EntityId, Adventurer] = Field(default_factory=dict)


def read(state: GameState) -> Mechanics:
    return Mechanics.model_validate(state.mechanics)


def write(state: GameState, mechanics: Mechanics) -> None:
    write_mechanics(state, mechanics)


def begin(state: GameState, rules: Mapping[EntityId, Rules]) -> None:
    actors: dict[EntityId, Adventurer] = {}
    for entity in state.world.entities.values():
        authored = rules.get(entity.id)
        if entity.kind != "actor":
            if authored:
                raise ValueError(f"story writes mechanics for actors only, not {entity.id!r}")
            continue
        actors[entity.id] = Adventurer.model_validate(authored or {})
    write(state, Mechanics(actors=actors))


def commit(state: GameState) -> None:
    """An actor who joined the world mid-turn is given their numbers by the commit that admits
    them; a payload missing the player is corruption, not a gap to fill."""
    mechanics = read(state)
    if PLAYER_ID not in mechanics.actors:
        raise ValueError("the story mechanics name no player")
    for entity in state.world.of_kind("actor"):
        _ = mechanics.actors.setdefault(entity.id, Adventurer())
    if gone := sorted(set(mechanics.actors) - state.world.all_ids()):
        raise ValueError(f"mechanics name actors the world does not hold: {gone}")
    write(state, mechanics)


def render(state: GameState) -> EntityRenderer:
    mechanics = read(state)
    return lambda entity: describe(mechanics, entity)


def describe(mechanics: Mechanics, entity: Entity) -> str:
    actor = mechanics.actors.get(entity.id)
    if actor is None:
        return ""
    approaches = ", ".join(f"{name} {actor.approach(name)}" for name in APPROACHES)
    return f"approaches: {approaches}\npools: {render_counters(actor.counters())}"


def apply(draft: GameState, effect: StoryEffect) -> list[Fact]:
    if not isinstance(effect, CounterChange):
        return apply_effect(draft, effect)
    mechanics = read(draft)
    entity, seen = reveal_target(draft, effect.entity_id)
    facts = [*seen, *_move_pool(mechanics, entity, effect)]
    write(draft, mechanics)
    return facts


def _move_pool(mechanics: Mechanics, entity: Entity, effect: CounterChange) -> list[Fact]:
    actor = mechanics.actors.get(entity.id)
    counter = None if actor is None else actor.counters().get(effect.counter)
    if counter is None:
        known = ", ".join(sorted(actor.counters())) if actor else "(none)"
        raise ValueError(f"{entity.name} has no pool {effect.counter!r}. Their pools are: {known}")
    if effect.mode == "adjust":
        return adjust(entity, effect.counter, counter, effect.amount, effect.why)
    return spend(entity, effect.counter, counter, effect.amount, effect.why)
