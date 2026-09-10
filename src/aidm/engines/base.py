from abc import abstractmethod
from collections.abc import Iterable, Mapping, Sequence
from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Frozen, Mutable, Refusal
from aidm.core.facts import DiceEvent, Fact
from aidm.core.play import Exchange, SceneRecord
from aidm.core.views import Pairs, Panel, PanelRow, Subject

PLAYER_ID = EntityId("player")
CHANGE_WORLD = (
    "Call this when the story has settled a change to the world. Fill the fields of the verb "
    "you pick. One call makes one change."
)
UNKNOWN_ID = "unknown id {entity_id!r}. Use only the ids you were shown."
IS_DEAD = "{name} is dead and takes no further part."

type Chattiness = Literal["quiet", "normal", "chatty"]


class Thing(Mutable):
    id: CheckedEntityId
    name: str
    brief: str
    known: bool = False

    @property
    def mention(self) -> str:
        """Carries the exact id so a role can reuse it."""
        return f"the player {self.tag}" if self.id == PLAYER_ID else self.tag

    @property
    def tag(self) -> str:
        return self.subject().tag

    @property
    def headline(self) -> str:
        return self.subject().headline

    @property
    def met_label(self) -> str:
        return "met" if self.known else "unmet"

    def rows(self) -> Pairs:
        return ()

    def line(self, *, rows: Pairs | None = None, detail: str = "") -> str:
        parts = [f"- {self.headline}"]
        shown = self.rows() if rows is None else rows
        if sheet := "; ".join(f"{label.lower()}: {value}" for label, value in shown):
            parts.append(f"  {sheet}")
        if detail:
            parts.append(f"  {detail}")
        return "\n".join(parts)

    def fact(
        self,
        trace: str,
        *,
        narrate: bool = True,
        card: str = "",
        dice: tuple[DiceEvent, ...] = (),
    ) -> Fact:
        """`told` only when the player has learned of this thing, so no unknown name leaks."""
        return Fact(trace=trace, told=narrate and self.known, card=card, dice=dice)

    def reveal(self, *, card: str = "") -> list[Fact]:
        """Leave cards to the containing action or the standalone reveal arm."""
        if self.known:
            return []
        self.known = True
        return [self.fact(f"learned of {self.mention}", card=card)]

    def subject(self) -> Subject:
        return Subject(id=self.id, label=self.name, detail=self.brief)


class Person(Thing):
    alive: bool = True
    chattiness: Chattiness = Field(
        default="normal",
        description="How readily they speak unprompted when travelling with the player. Most "
        "are normal.",
    )

    @property
    def headline(self) -> str:
        return super().headline + ("" if self.alive else " (dead)")

    def unwritten(self) -> str:
        """What the worldsmith may not write into a fresh cast member; empty when nothing."""
        return "" if self.alive else "alive"


class World[P: Person](Mutable):
    player: P
    source: str = ""
    party: list[EntityId] = Field(default_factory=list)

    @abstractmethod
    def records(self) -> tuple[SceneRecord, ...]: ...
    @abstractmethod
    def record(self, exchange: Exchange) -> None: ...
    @abstractmethod
    def members(self) -> Sequence[Person]: ...

    def exchanges(self) -> tuple[Exchange, ...]:
        return tuple(exchange for record in self.records() for exchange in record.exchanges)

    def join(self, member: Person) -> list[Fact]:
        if member.id in self.party:
            raise Refusal(f"{member.name} already travels with the player")
        facts = member.reveal()
        self.party.append(member.id)
        trace = f"{member.tag} travels with the player"
        facts.append(member.fact(trace, card=f"{member.name} joins your party"))
        return facts

    def part(self, member: Person) -> list[Fact]:
        if member.id not in self.party:
            raise Refusal(f"{member.name} does not travel with the player")
        self.party.remove(member.id)
        trace = f"{member.tag} no longer travels with the player"
        return [member.fact(trace, card=f"{member.name} leaves your party")]


class JoinParty(Frozen):
    """A character here starts travelling with the player."""

    verb: Literal["join_party"]
    entity_id: CheckedEntityId = Field(description="Exact id of who is joining.")


class LeaveParty(Frozen):
    """A party member stops travelling with the player."""

    verb: Literal["leave_party"]
    entity_id: CheckedEntityId = Field(description="Exact id of the party member leaving.")


class ChangeWorld[C](Frozen):
    change: C = Field(description="The change to apply. `verb` picks which one.")


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

    def __str__(self) -> str:
        return f"{self.current}/{self.maximum}"

    @property
    def shortfall(self) -> int:
        return self.maximum - self.current

    def adjust(self, amount: int) -> int:
        before = self.current
        self.current = min(max(before + amount, 0), self.maximum)
        return self.current - before

    def change(self, owner: Thing, amount: int, label: str, why: str) -> list[Fact]:
        delta = self.adjust(amount)
        if delta == 0:
            return []
        moved = f"{label} {delta:+d} -> {self}"
        card = moved if owner.id == PLAYER_ID else f"{owner.name}: {moved}"
        return [owner.fact(f"{owner.mention} {moved} ({why})", card=card)]


def character_panel(rows: Pairs) -> Panel:
    return Panel(
        title="Character",
        rows=tuple(PanelRow(label=label, detail=detail) for label, detail in rows),
    )


def here_panel(others: Iterable[Subject]) -> Panel:
    """Who else: the player already has the sheet above, so a row for them would say it twice."""
    return Panel(title="Also here", rows=tuple(other.row() for other in others))


def party_section(members: Sequence[Thing]) -> Pairs:
    if not members:
        return ()
    return (("THE PARTY (led by the player)", "\n".join(member.line() for member in members)),)


def party_panel(members: Sequence[Thing]) -> tuple[Panel, ...]:
    if not members:
        return ()
    rows = tuple(
        row
        for member in members
        for row in (
            member.subject().row(),
            *(PanelRow(label=label, detail=detail) for label, detail in member.rows()),
        )
    )
    return (Panel(title="Party", rows=rows),)


def trail_panel(titles: Iterable[str]) -> Panel:
    return Panel(title="Trail", rows=tuple(PanelRow(label=title, detail="") for title in titles))


def check_filing(pool: Mapping[EntityId, Thing]) -> None:
    for key, entity in pool.items():
        if key != entity.id:
            raise Refusal(f"entity {entity.id!r} is filed under {key!r}")
