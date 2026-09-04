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


class Thing(Mutable):
    """What every world thing shares: an id, a name, a brief, and whether the player has met it."""

    id: CheckedEntityId
    name: str
    brief: str
    known: bool = False

    @property
    def label(self) -> str:
        """Name and exact id, so a role can reuse the id; the player is named as such."""
        if self.id == PLAYER_ID:
            return f"the player {self.name}[{self.id}]"
        return f"{self.name}[{self.id}]"

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

    def reveal(self) -> list[Fact]:
        """Leave cards to the containing action or the standalone reveal arm."""
        if self.known:
            return []
        self.known = True
        return [self.fact("entity_discovered", f"learned of {self.label}")]

    def subject(self) -> Subject:
        return Subject(id=self.id, name=self.name, brief=self.brief)


class Person(Thing):
    """Every cast entry and every player sheet."""

    alive: bool = True

    def rows(self) -> Rows:
        """The sheet, as the master's entity line prints it."""
        return ()

    def unwritten(self) -> str:
        """What the worldsmith may not write into a fresh cast member; empty when nothing."""
        return "" if self.alive else "alive"

    def line(self, *, detail: str = "") -> str:
        line = f"- {self.name}[{self.id}] — {self.brief}"
        if not self.alive:
            line += " (dead)"
        parts = [line]
        if sheet := "; ".join(f"{label.lower()}: {value}" for label, value in self.rows()):
            parts.append(f"  {sheet}")
        if detail:
            parts.append(f"  {detail}")
        return "\n".join(parts)


class Pack(Frozen):
    """What every table set carries; an engine's own `Pack` extends it."""

    name: str


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
