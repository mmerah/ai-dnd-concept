from abc import abstractmethod
from collections.abc import Iterable, Mapping, Sequence
from random import Random
from typing import Self

from pydantic import BaseModel, Field, model_validator

from aidm.core.entities import Frozen, Mutable, Refusal, Slug, check_unique
from aidm.core.facts import DiceEvent, Fact, roll
from aidm.core.prompt import Sections, sections
from aidm.core.tools import schema_text
from aidm.core.views import Chattiness, Panel, PanelRow, Rows, Subject

PLAYER_ID: Slug = "player"
REVEAL = "A hidden entity here becomes known to the player."
KILL = "Someone here dies."
JOIN_PARTY = "A character here starts travelling with the player."
LEAVE_PARTY = "A party member stops travelling with the player."
UNKNOWN_ID = "unknown id {entity_id!r}. Use only the ids you were shown."
IS_DEAD = "{name} is dead and takes no further part."
SOURCELESS = "(none — write from what is below)"


class Gauge(Mutable):
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


class Thing(Mutable):
    id: Slug
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

    def rows(self) -> Rows:
        return ()

    def line(self, *, rows: Rows | None = None, detail: str = "") -> str:
        parts = [f"- {self.headline}"]
        shown = self.rows() if rows is None else rows
        if sheet := "; ".join(f"{label.lower()}: {value}" for label, value in shown):
            parts.append(f"  {sheet}")
        if detail:
            parts.append(f"  {detail}")
        return "\n".join(parts)

    def fact(self, trace: str, *, card: str = "", dice: tuple[DiceEvent, ...] = ()) -> Fact:
        """`told` only when the player has learned of this thing, so no unknown name leaks."""
        return Fact(trace=trace, told=self.known, card=card, dice=dice)

    def change(self, gauge: Gauge, amount: int, label: str, why: str) -> list[Fact]:
        delta = gauge.adjust(amount)
        if delta == 0:
            return []
        moved = f"{label} {delta:+d} → {gauge}"
        card = moved if self.id == PLAYER_ID else f"{self.name}: {moved}"
        return [self.fact(f"{self.mention} {moved} ({why})", card=card)]

    def reveal(self, *, card: str = "") -> list[Fact]:
        """Leave cards to the containing action or the standalone `reveal` tool."""
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

    def forbidden(self) -> str:
        """What the worldsmith may not write into a fresh cast member; empty when nothing."""
        return "" if self.alive else "alive"

    @property
    def hired(self) -> bool:
        """Whether they carry a sheet. A kind that never does answers no."""
        return False

    @property
    def hireable(self) -> bool:
        """Whether a sheet could still be written for them."""
        return False


class Sheet(Mutable):
    """What a person's dice are written on."""

    def rows(self) -> Rows:
        return ()


class Sheeted[S: Sheet](Person):
    sheet: S | None = Field(default=None, description="Leave empty.")

    def require_sheet(self) -> S:
        if self.sheet is None:
            raise Refusal(f"{self.name} carries no dice")
        return self.sheet

    def rows(self) -> Rows:
        return self.sheet.rows() if self.sheet is not None else ()

    def carried(self) -> str:
        return ""

    def line(self, *, rows: Rows | None = None, detail: str = "") -> str:
        if self.id != PLAYER_ID and (carried := self.carried()):
            detail = "; ".join(part for part in (detail, carried) if part)
        return super().line(rows=rows, detail=detail)

    def forbidden(self) -> str:
        parts = (super().forbidden(), "a sheet" if self.sheet is not None else "")
        return ", ".join(part for part in parts if part)

    @property
    def hired(self) -> bool:
        return self.sheet is not None

    @property
    def hireable(self) -> bool:
        return self.sheet is None


class Item(Mutable):
    name: str

    def notes(self) -> str:
        return ""


class ItemSheet[I: Item](Sheet):
    items: dict[Slug, I] = Field(default_factory=dict)

    def require(self, item_id: Slug, owner: str) -> I:
        item = self.items.get(item_id)
        if item is None:
            raise Refusal(f"{item_id!r} is not among {owner}'s items")
        return item

    def drop_item(self, item_id: Slug, owner: Thing) -> list[Fact]:
        item = self.require(item_id, owner.name)
        del self.items[item_id]
        return [owner.fact(f"{owner.mention} drops {item.name}", card=f"Dropped {item.name}")]


class World[M: Person, P: Person](Mutable):
    player: P
    source: str = ""
    party: list[Slug] = Field(default_factory=list)

    @model_validator(mode="after")
    def _player_carries_a_sheet(self) -> Self:
        if self.player.hireable:
            raise ValueError("the player carries no sheet")
        return self

    @model_validator(mode="after")
    def _party_travels(self) -> Self:
        check_unique("party", self.party)
        if self.player.id in self.party:
            raise ValueError("the player cannot travel with themselves")
        for member_id in self.party:
            member = self.member_of(member_id)
            if member is None or not member.known:
                raise ValueError(f"{member_id!r} travels with the player but is not known")
            if not member.alive:
                raise ValueError(f"{member_id!r} is dead and cannot travel with the player")
        return self

    @abstractmethod
    def members(self) -> Sequence[M]: ...
    @abstractmethod
    def member_of(self, member_id: Slug) -> M | None: ...
    @abstractmethod
    def require_member_here(self, entity_id: Slug) -> M:
        """Alive and here with the player."""

    @abstractmethod
    def reveal_hidden(self, entity_id: Slug) -> list[Fact]: ...
    @abstractmethod
    def kill(self, entity_id: Slug) -> list[Fact]: ...
    @abstractmethod
    def leave_party(self, entity_id: Slug) -> list[Fact]: ...

    def join_party(self, entity_id: Slug) -> list[Fact]:
        return self.join(self.require_member_here(entity_id))

    def require_actor(self, actor_id: Slug | None) -> M | P:
        if actor_id is None or actor_id == self.player.id:
            return self.player
        member = self.require_member_here(actor_id)
        if member.hired and member.id in self.party:
            return member
        raise Refusal(f"{member.name} is not the player or a hired party member")

    def require_hireable(self, entity_id: Slug) -> M:
        member = self.require_member_here(entity_id)
        if member.hired:
            raise Refusal(f"{member.name} already carries a sheet")
        return member

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

    def sheet_rows(self) -> Rows:
        """Overridable: a rule may amend a row."""
        return self.player.rows()


class Attempt(Frozen):
    """An attempt at something uncertain."""

    what: str = Field(
        min_length=1,
        description="The attempt, in a few words the player reads.",
    )


class Reveal(Frozen):
    entity_id: Slug = Field(description="Exact id of something hidden here.")


class Kill(Frozen):
    entity_id: Slug = Field(description="Exact id of who here died.")


class JoinParty(Frozen):
    entity_id: Slug = Field(description="Exact id of who is joining.")


class LeaveParty(Frozen):
    entity_id: Slug = Field(description="Exact id of the party member leaving.")


def character_panel(rows: Rows) -> Panel:
    return Panel(
        title="Character",
        rows=tuple(PanelRow(label=label, detail=detail) for label, detail in rows),
    )


def here_panel(others: Iterable[Subject]) -> Panel:
    """Who else: the player already has the sheet above, so a row for them would say it twice."""
    return Panel(title="Also here", rows=tuple(other.row() for other in others))


def party_section(members: Sequence[Thing]) -> Sections:
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


def check_filing(pool: Mapping[Slug, Thing]) -> None:
    for key, entity in pool.items():
        if key != entity.id:
            raise Refusal(f"entity {entity.id!r} is filed under {key!r}")


def banded(face: int, low: str, mid: str, high: str) -> str:
    """The three bands of a six-sided read: 1 to 2, 3 to 4, 5 and up."""
    return low if face <= 2 else mid if face <= 4 else high


def luck_test(question: str, die: int, bands: tuple[str, str, str], rng: Random) -> list[Fact]:
    """A question about the world when nobody acts: the dice trace, the answer is never told."""
    rolled = roll((die,), question, rng)
    result = banded(rolled.face, *bands)
    return [rolled.fact, Fact(trace=f"{question} — d{die} [{rolled.face}] → {result}")]


def render_worldsmith(
    *,
    role: str,
    source: str,
    scope: str,
    family: Sections,
    intent: str,
    guidance: str,
    answer: type[BaseModel],
) -> str:
    return sections(
        (
            ("YOUR ROLE", role),
            ("SOURCE MATERIAL", source or SOURCELESS),
            ("THE SCOPE OF PLAY", scope),
            *family,
            ("WHAT COMES NEXT", intent),
            ("ENGINE GUIDANCE", guidance),
            ("ANSWER WITH", schema_text(answer)),
        )
    )
