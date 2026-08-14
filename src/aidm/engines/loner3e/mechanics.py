from typing import Annotated

from pydantic import Field, TypeAdapter

from aidm.engines.counters import (
    CounterChange,
    adjust,
    read_mechanics,
    render_counters,
    spend,
    write_mechanics,
)
from aidm.state.apply import apply_effect, reveal_target
from aidm.state.base import Counter, Entity, EntityId, Mutable, Slug
from aidm.state.creation import ContentSlug
from aidm.state.effects import WorldOp
from aidm.state.facts import Fact
from aidm.state.world import GameState

from .pack import SRD_PACK

LUCK_MAX = 6
TIES_PER_TWIST = 3

type Loner3eEffect = Annotated[WorldOp | CounterChange, Field(discriminator="op")]
EFFECTS: TypeAdapter[Loner3eEffect] = TypeAdapter(Loner3eEffect)


class Sheet(Mutable):
    """The one sheet shape, whether it belongs to the player or to an NPC."""

    # The table set this character was built from; the twist table is read from it.
    pack: ContentSlug = SRD_PACK
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
    mechanics = read_mechanics(draft, Mechanics)
    entity, seen = reveal_target(draft, effect.entity_id)
    facts = [*seen, *_move_pool(mechanics, entity, effect)]
    write_mechanics(draft, mechanics)
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
