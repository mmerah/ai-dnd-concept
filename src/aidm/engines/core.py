from collections.abc import Mapping, Sequence
from pathlib import Path
from random import Random
from typing import Literal, Protocol, Self

from pydantic import BaseModel, Field, model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Frozen, Mutable, require_unique
from aidm.core.facts import DiceEvent, Fact, roll
from aidm.core.io import ENCODING
from aidm.core.play import DecisionOption
from aidm.core.views import Panel, PanelRow, Rows

PLAYER_ID = EntityId("player")
PLAYER_DEAD = "the player is dead; they take no further part."
CHANGE_WORLD = (
    "Apply one settled world change to match the story. Set `verb` to pick the change and fill "
    "that verb's own fields. One call makes one change."
)


class Entity(Protocol):
    """What every world thing shares: an id, a name, and whether the player has met it."""

    @property
    def id(self) -> EntityId: ...
    @property
    def name(self) -> str: ...

    known: bool


class Person(Mutable):
    """Every cast entry and every player sheet."""

    id: CheckedEntityId
    name: str
    brief: str
    known: bool = False
    alive: bool = True

    def rows(self) -> Rows:
        """The sheet, as the master's entity line prints it."""
        return ()

    def unwritten(self) -> str:
        """What the worldsmith may not write into a fresh cast member; empty when nothing."""
        return "" if self.alive else "alive"


class Pack(Frozen):
    """What every table set carries; an engine's own `Pack` extends it."""

    name: str


class JoinParty(Frozen):
    """A character here starts travelling with the player."""

    verb: Literal["join_party"]
    entity_id: CheckedEntityId = Field(description="Exact id of who is joining.")


class LeaveParty(Frozen):
    """A companion stops travelling with the player."""

    verb: Literal["leave_party"]
    entity_id: CheckedEntityId = Field(description="Exact id of the companion leaving.")


class Counter(Mutable):
    current: int
    maximum: int

    @model_validator(mode="after")
    def _within_bounds(self) -> Self:
        if self.current < 0:
            raise ValueError(f"{self.current} is below zero")
        if self.current > self.maximum:
            raise ValueError(f"{self.current} is above maximum {self.maximum}")
        return self

    def clamped(self, value: int) -> int:
        return min(max(value, 0), self.maximum)


def sentence(text: str) -> str:
    return text[:1].upper() + text[1:]


def join_party(party: list[EntityId], one: Person) -> Fact:
    if one.id in party:
        raise ValueError(f"{one.name} already travels with the player")
    party.append(one.id)
    return entity_fact(
        one,
        "party_joined",
        f"{one.name}[{one.id}] travels with the player",
        card=f"{one.name} joins your party",
    )


def leave_party(party: list[EntityId], one: Person) -> Fact:
    if one.id not in party:
        raise ValueError(f"{one.name} does not travel with the player")
    party.remove(one.id)
    return entity_fact(
        one,
        "party_left",
        f"{one.name}[{one.id}] no longer travels with the player",
        card=f"{one.name} leaves your party",
    )


def check_party(party: Sequence[EntityId], cast: Mapping[EntityId, Person]) -> None:
    require_unique("party", party)
    for one in party:
        if one not in cast:
            raise ValueError(f"{one!r} travels with the player but is not in the cast")
        if not cast[one].alive:
            raise ValueError(f"{one!r} is dead and cannot travel with the player")


def party_rows(members: Sequence[Person]) -> Rows:
    if not members:
        return ()
    return (("THE PARTY (led by the player)", "\n".join(f"- {m.name}[{m.id}]" for m in members)),)


def party_panel(members: Sequence[Person]) -> tuple[Panel, ...]:
    if not members:
        return ()
    rows = tuple(PanelRow(label=m.name, detail=m.brief, icon_id=m.id) for m in members)
    return (Panel(title="Party", rows=rows),)


def pool(counter: Counter) -> str:
    return f"{counter.current}/{counter.maximum}"


def adjust(counter: Counter, amount: int) -> int:
    """Move a bounded pool and say how far it moved; a clamp can land short of `amount`."""
    before = counter.current
    counter.current = counter.clamped(before + amount)
    return counter.current - before


def counter_fact(
    one: Entity, counter: Counter, amount: int, label: str, why: str, player_id: EntityId
) -> list[Fact]:
    landed = adjust(counter, amount)
    if landed == 0:
        return []
    moved = f"{label} {landed:+d} -> {pool(counter)}"
    card = moved if one.id == player_id else f"{one.name}: {moved}"
    trace = f"{labeled(one, player_id)} {moved} ({why})"
    return [entity_fact(one, "counter_changed", trace, card=card)]


def check_filing[E: Entity](pool: dict[EntityId, E]) -> None:
    for key, one in pool.items():
        if key != one.id:
            raise ValueError(f"entity {one.id!r} is filed under {key!r}")


def labeled(entity: Entity, player_id: EntityId) -> str:
    """A trace names an entity by name and exact id, so the model can reuse the id."""
    if entity.id == player_id:
        return f"the player {entity.name}[{entity.id}]"
    return f"{entity.name}[{entity.id}]"


def entity_fact(
    entity: Entity,
    kind: str,
    trace: str,
    *,
    narrate: bool = True,
    card: str = "",
    dice: tuple[DiceEvent, ...] = (),
) -> Fact:
    """An entity the player has not learned of narrates nothing, so no unknown name leaks."""
    return Fact(
        kind=kind,
        trace=trace,
        told=narrate and entity.known,
        entity_id=entity.id,
        card=card,
        dice=dice,
    )


def reveal(entity: Entity, player_id: EntityId) -> list[Fact]:
    """Leave cards to the containing action or the standalone reveal arm."""
    if entity.known:
        return []
    entity.known = True
    return [entity_fact(entity, "entity_discovered", f"learned of {labeled(entity, player_id)}")]


def keep_highest(
    faces: Sequence[int], reason: str, rng: Random, *, label: str
) -> tuple[int, DiceEvent, Fact]:
    rolled, fact = roll(faces, reason, rng)
    kept = max(rolled)
    event = DiceEvent(
        label=label, faces=tuple(faces), rolled=rolled, highlight=(rolled.index(kept),)
    )
    return kept, event, fact


def pack_options(packs: Mapping[str, Pack]) -> tuple[DecisionOption, ...]:
    """The create page's table sets, and the first step of every scene engine's creation."""
    return tuple(DecisionOption(id=key, label=one.name) for key, one in packs.items())


def load_packs[P: BaseModel](directories: Sequence[Path], model: type[P]) -> dict[str, P]:
    """Later directories win; a broken file raises rather than being skipped."""
    packs: dict[str, P] = {}
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            packs[path.stem] = model.model_validate_json(path.read_text(encoding=ENCODING))
    return packs
