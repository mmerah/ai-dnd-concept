import re
from abc import abstractmethod
from collections.abc import Iterable, Mapping, Sequence
from typing import ClassVar, Self

from pydantic import Field, model_validator

from aidm.core.entities import Mutable, Refusal, Slug, check_unique, headline_of, tag_of
from aidm.core.facts import DiceEvent, Fact
from aidm.core.prompt import Sections
from aidm.core.views import Chattiness, Panel, PanelRow, Rows, Subject

PLAYER_ID: Slug = "player"
UNKNOWN_ID = "unknown id {entity_id!r}. Use only the ids you were shown."
IS_DEAD = "{name} is dead and takes no further part."
NO_DICE = "{name} carries no dice"
NOT_AN_ACTOR = "{name} is not the player or a hired party member"


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
    name: str = Field(min_length=1)
    brief: str
    known: bool = False

    @property
    def mention(self) -> str:
        return f"the player {self.tag}" if self.id == PLAYER_ID else self.tag

    @property
    def tag(self) -> str:
        return tag_of(self.name, self.id)

    @property
    def headline(self) -> str:
        return headline_of(self.name, self.id, self.brief)

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

    def card_line(self, line: str, *, leads: bool | None = None) -> str:
        if leads is None:
            leads = self.id == PLAYER_ID
        return line if leads else f"{self.name}: {line}"

    def change(self, gauge: Gauge, amount: int, label: str, why: str) -> list[Fact]:
        delta = gauge.adjust(amount)
        if delta == 0:
            return []
        moved = f"{label} {delta:+d} → {gauge}"
        return [self.fact(f"{self.mention} {moved} ({why})", card=self.card_line(moved))]

    def reveal(self, *, card: str = "") -> list[Fact]:
        if self.known:
            return []
        self.known = True
        return [self.fact(f"learned of {self.mention}", card=card)]

    def subject(self) -> Subject:
        return Subject(id=self.id, name=self.name, brief=self.brief)


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

    @property
    def hired(self) -> bool:
        return False

    def required(self) -> str:
        """What a new cast member must be for the worldsmith to write it; empty when nothing."""
        return "" if self.alive else "alive"

    def changed_tags(
        self, kind: str, current: Sequence[str], gained: Sequence[str], lost: Sequence[str]
    ) -> list[str]:
        check_unique(f"{kind} tags", (*gained, *lost))
        if carried := [tag for tag in gained if tag in current]:
            raise Refusal(f"{self.name} already carries the {kind} {carried[0]!r}")
        if missing := [tag for tag in lost if tag not in current]:
            raise Refusal(f"{self.name} carries no {kind} {missing[0]!r}")
        return [tag for tag in (*current, *gained) if tag not in lost]


class World[M: Person](Mutable):
    tempo: ClassVar[int]  # counted turns between two firings of the meanwhile clock

    player: M
    party: list[Slug] = Field(default_factory=list)
    turns_played: int = Field(default=0, ge=0)  # counted turns since the last fire
    meanwhile_due: bool = False  # the clock has fired and nothing has spent it yet

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
    def unmet(self) -> Iterable[Thing]: ...

    def require_actor(self, actor_id: Slug | None) -> M:
        if actor_id is None or actor_id == self.player.id:
            return self.player
        member = self.require_member_here(actor_id)
        if member.hired and member.id in self.party:
            return member
        raise Refusal(NOT_AN_ACTOR.format(name=member.name))

    def leave_party(self, entity_id: Slug) -> list[Fact]:
        member = self.member_of(entity_id)
        if member is None:
            raise Refusal(UNKNOWN_ID.format(entity_id=entity_id))
        if member.id not in self.party:
            raise Refusal(f"{member.name} does not travel with the player")
        self.party.remove(member.id)
        trace = f"{member.tag} no longer travels with the player"
        return [member.fact(trace, card=f"{member.name} leaves your party")]

    def check_unnamed(self, *texts: str) -> None:
        if leaked := sorted(set(named_unmet("\n".join(texts), self.unmet()))):
            raise Refusal(f"this names what the player has not met: {leaked}. Say it another way.")

    def tick(self, *, counted: bool) -> None:
        if not counted:
            return
        self.turns_played += 1
        if self.turns_played >= self.tempo:
            self.turns_played = 0
            self.meanwhile_due = True

    def disarm(self) -> None:
        self.meanwhile_due = False

    def join_party(self, entity_id: Slug) -> list[Fact]:
        return self.join(self.require_member_here(entity_id))

    def join(self, member: Person) -> list[Fact]:
        if member.id in self.party:
            raise Refusal(f"{member.name} already travels with the player")
        self.party.append(member.id)
        trace = f"{member.tag} travels with the player"
        return [member.fact(trace, card=f"{member.name} joins your party")]

    def sheet_rows(self) -> Rows:
        return self.player.rows()


def character_panel(rows: Rows) -> Panel:
    return Panel(
        title="Character",
        portrait=True,
        rows=tuple(PanelRow(name=name, brief=brief) for name, brief in rows),
    )


def here_panel(others: Iterable[Subject]) -> Panel:
    """The player already has the sheet above, so a row for them would say it twice."""
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
            *(PanelRow(name=name, brief=brief) for name, brief in member.rows()),
        )
    )
    return (Panel(title="Party", rows=rows),)


def trail_panel(titles: Iterable[str]) -> Panel:
    return Panel(title="Trail", rows=tuple(PanelRow(name=title, brief="") for title in titles))


def joined(*parts: str) -> str:
    return ", ".join(part for part in parts if part)


def check_filing(pool: Mapping[Slug, Thing]) -> None:
    for key, entity in pool.items():
        if key != entity.id:
            raise Refusal(f"entity {entity.id!r} is filed under {key!r}")


def required_needs(pool: Mapping[Slug, Person], filed: Iterable[Slug]) -> list[str]:
    already = set(filed)
    return [
        f"{entity_id}: {why}"
        for entity_id, entry in pool.items()
        if entity_id not in already and (why := entry.required())
    ]


def named_unmet(text: str, entities: Iterable[Thing]) -> list[str]:
    folded = text.casefold()
    return [
        entity.name
        for entity in entities
        if (name := entity.name.strip().casefold())
        and re.search(rf"(?<!\w){re.escape(name)}(?!\w)", folded) is not None
    ]


def leaked_names(read: str, things: Iterable[Thing], hidden: Sequence[Thing]) -> set[str]:
    """No text the player may read names something hidden; nothing watches itself."""
    leaked = set(named_unmet(read, hidden))
    for thing in things:
        text = "\n".join((thing.brief, *(value for _, value in thing.rows())))
        leaked.update(named_unmet(text, (other for other in hidden if other.id != thing.id)))
    return leaked
