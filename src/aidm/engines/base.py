from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from random import Random
from typing import Self

from pydantic import BaseModel, model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Frozen, Mutable, Refusal, Slug, parse
from aidm.core.facts import DiceEvent, Fact, roll
from aidm.core.io import ENCODING, decode
from aidm.core.views import Panel, PanelRow, Rows, Subject

PLAYER_ID = EntityId("player")
SRD_PACK: Slug = "srd"
CHANGE_WORLD = (
    "Apply one settled world change to match the story. Set `verb` to pick the change and fill "
    "that verb's own fields. One call makes one change."
)
UNKNOWN_ID = "unknown id {entity_id!r}. Use only ids you were shown."
IS_DEAD = "{name} is dead; they take no further part."


class Thing(Mutable):
    id: CheckedEntityId
    name: str
    brief: str
    known: bool = False

    @property
    def label(self) -> str:
        """Name and exact id, so a role can reuse the id; the player is named as such."""
        if self.id == PLAYER_ID:
            return f"the player {self.tag}"
        return self.tag

    @property
    def tag(self) -> str:
        return f"{self.name}[{self.id}]"

    @property
    def headline(self) -> str:
        return self.tag + (f" — {self.brief}" if self.brief else "")

    def rows(self) -> Rows:
        """The sheet, as the master's entity line prints it."""
        return ()

    def line(self, *, rows: Rows | None = None, detail: str = "") -> str:
        """The master's entity line, then the sheet, then a detail; `rows` overrides the sheet."""
        parts = [f"- {self.headline}"]
        shown = self.rows() if rows is None else rows
        if sheet := "; ".join(f"{label.lower()}: {value}" for label, value in shown):
            parts.append(f"  {sheet}")
        if detail:
            parts.append(f"  {detail}")
        return "\n".join(parts)

    def fact(
        self,
        kind: str,
        trace: str,
        *,
        narrate: bool = True,
        card: str = "",
        dice: tuple[DiceEvent, ...] = (),
    ) -> Fact:
        """`told` only when the player has learned of this thing, so no unknown name leaks."""
        return Fact(kind=kind, trace=trace, told=narrate and self.known, card=card, dice=dice)

    def reveal(self, *, card: str = "") -> list[Fact]:
        """Leave cards to the containing action or the standalone reveal arm."""
        if self.known:
            return []
        self.known = True
        return [self.fact("entity_discovered", f"learned of {self.label}", card=card)]

    def subject(self) -> Subject:
        return Subject(id=self.id, name=self.name, brief=self.brief)


class Person(Thing):
    alive: bool = True

    @property
    def headline(self) -> str:
        return super().headline + ("" if self.alive else " (dead)")

    def unwritten(self) -> str:
        """What the worldsmith may not write into a fresh cast member; empty when nothing."""
        return "" if self.alive else "alive"


class Pack(Frozen):
    name: str
    source: str
    license: str


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
        """Move a bounded pool and say how far it moved; a clamp can land short of `amount`."""
        before = self.current
        self.current = min(max(before + amount, 0), self.maximum)
        return self.current - before

    def change(self, owner: Thing, amount: int, label: str, why: str) -> list[Fact]:
        """The move as a fact on its owner; a zero move is no fact."""
        delta = self.adjust(amount)
        if delta == 0:
            return []
        moved = f"{label} {delta:+d} -> {self}"
        card = moved if owner.id == PLAYER_ID else f"{owner.name}: {moved}"
        return [owner.fact("counter_changed", f"{owner.label} {moved} ({why})", card=card)]


def sentence(text: str) -> str:
    return text[:1].upper() + text[1:]


def character_panel(rows: Rows) -> Panel:
    return Panel(
        title="Character",
        rows=tuple(PanelRow(label=label, detail=detail) for label, detail in rows),
    )


def here_panel(player: Subject, others: Iterable[Subject]) -> Panel:
    """Free: two families build it from subjects, not from a world."""
    rows = (
        PanelRow(label=f"{player.name} (you)", detail=player.brief, icon_id=player.id),
        *(PanelRow(label=other.name, detail=other.brief, icon_id=other.id) for other in others),
    )
    return Panel(title="Here", rows=rows)


def trail_panel(titles: Iterable[str]) -> Panel:
    return Panel(title="Trail", rows=tuple(PanelRow(label=title, detail="") for title in titles))


def check_filing(pool: Mapping[EntityId, Thing]) -> None:
    for key, entity in pool.items():
        if key != entity.id:
            raise Refusal(f"entity {entity.id!r} is filed under {key!r}")


def keep_highest(
    faces: Sequence[int], reason: str, rng: Random, *, label: str
) -> tuple[int, DiceEvent, Fact]:
    rolled, fact = roll(faces, reason, rng)
    kept = max(rolled)
    event = DiceEvent(
        label=label, faces=tuple(faces), rolled=rolled, highlight=(rolled.index(kept),)
    )
    return kept, event, fact


def read_packs[P: BaseModel](directory: Path, model: type[P]) -> dict[str, P]:
    """A broken file raises rather than being skipped."""
    return {
        path.stem: parse(model, decode(path.read_text(encoding=ENCODING)))
        for path in sorted(directory.glob("*.json"))
    }
