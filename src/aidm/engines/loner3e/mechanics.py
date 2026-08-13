from collections.abc import Mapping
from typing import Annotated

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

LUCK_MAX = 6
TIES_PER_TWIST = 3

type Loner3eEffect = Annotated[WorldOp | CounterChange, Field(discriminator="op")]


class Sheet(Mutable):
    """The one sheet shape, whether it belongs to the player or to an NPC."""

    concept: str = ""
    skills: tuple[str, ...] = ()
    frailties: tuple[str, ...] = ()
    gear: tuple[str, ...] = ()
    luck: Counter = Counter(current=LUCK_MAX, maximum=LUCK_MAX)
    milestones: Counter = Counter(current=0)

    def tags(self) -> tuple[str, ...]:
        return (*self.skills, *self.frailties, *self.gear)

    def counters(self) -> dict[Slug, Counter]:
        return {"luck": self.luck}


class Mechanics(Mutable):
    sheets: dict[EntityId, Sheet] = Field(default_factory=dict)
    # One tally for the whole game, as the note it fires says: a tie anywhere moves the same one.
    twist: Counter = Counter(current=0, maximum=TIES_PER_TWIST)


def read(state: GameState) -> Mechanics:
    return Mechanics.model_validate(state.mechanics)


def write(state: GameState, mechanics: Mechanics) -> None:
    write_mechanics(state, mechanics)


def begin(state: GameState, rules: Mapping[EntityId, Rules]) -> None:
    sheets: dict[EntityId, Sheet] = {}
    for entity in state.world.entities.values():
        authored = rules.get(entity.id)
        if entity.kind != "actor":
            if authored:
                raise ValueError(f"loner3e writes mechanics for actors only, not {entity.id!r}")
            continue
        sheets[entity.id] = Sheet.model_validate(authored or {})
    write(state, Mechanics(sheets=sheets))


def commit(state: GameState) -> None:
    """An actor who joined the world mid-turn is given their numbers by the commit that admits
    them; a payload missing the player is corruption, not a gap to fill."""
    mechanics = read(state)
    if PLAYER_ID not in mechanics.sheets:
        raise ValueError("the loner3e mechanics name no player")
    for entity in state.world.of_kind("actor"):
        _ = mechanics.sheets.setdefault(entity.id, Sheet())
    if gone := sorted(set(mechanics.sheets) - state.world.all_ids()):
        raise ValueError(f"mechanics name actors the world does not hold: {gone}")
    write(state, mechanics)


def render(state: GameState) -> EntityRenderer:
    mechanics = read(state)
    return lambda entity: describe(mechanics, entity)


def describe(mechanics: Mechanics, entity: Entity) -> str:
    sheet = mechanics.sheets.get(entity.id)
    if sheet is None:
        return ""
    lines = (
        f"concept: {sheet.concept}" if sheet.concept else "",
        f"skills: {', '.join(sheet.skills)}" if sheet.skills else "",
        f"frailties: {', '.join(sheet.frailties)}" if sheet.frailties else "",
        f"gear: {', '.join(sheet.gear)}" if sheet.gear else "",
        f"pools: {render_counters(sheet.counters())}",
    )
    return "\n".join(line for line in lines if line)


def apply(draft: GameState, effect: Loner3eEffect) -> list[Fact]:
    if not isinstance(effect, CounterChange):
        return apply_effect(draft, effect)
    mechanics = read(draft)
    entity, seen = reveal_target(draft, effect.entity_id)
    facts = [*seen, *_move_pool(mechanics, entity, effect)]
    write(draft, mechanics)
    return facts


def _move_pool(mechanics: Mechanics, entity: Entity, effect: CounterChange) -> list[Fact]:
    sheet = mechanics.sheets.get(entity.id)
    counter = None if sheet is None else sheet.counters().get(effect.counter)
    if counter is None:
        known = ", ".join(sorted(sheet.counters())) if sheet else "(none)"
        raise ValueError(f"{entity.name} has no pool {effect.counter!r}. Their pools are: {known}")
    if effect.mode == "adjust":
        return adjust(entity, effect.counter, counter, effect.amount, effect.why)
    return spend(entity, effect.counter, counter, effect.amount, effect.why)
