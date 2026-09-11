from collections.abc import Sequence
from random import Random
from typing import Self

from pydantic import model_validator

from aidm.core.entities import Frozen

NOTHING = "- (nothing changed)"


class DiceEvent(Frozen):
    label: str
    faces: tuple[int, ...]
    rolled: tuple[int, ...]
    highlight: tuple[int, ...] = ()

    @model_validator(mode="after")
    def _rolled_matches_faces(self) -> Self:
        if len(self.rolled) != len(self.faces):
            raise ValueError("one rolled value per face")
        for die, face in zip(self.rolled, self.faces, strict=True):
            if not 1 <= die <= face:
                raise ValueError(f"a d{face} cannot show {die}")
        for index in self.highlight:
            if not 0 <= index < len(self.rolled):
                raise ValueError(f"highlight {index} names no rolled die")
        return self


class Fact(Frozen):
    """One thing that occurred, rendered where its values were in scope."""

    trace: str
    told: bool = False
    card: str = ""
    dice: tuple[DiceEvent, ...] = ()


class Rolled(Frozen):
    rolled: tuple[int, ...]
    event: DiceEvent
    fact: Fact

    @property
    def kept(self) -> int:
        return max(self.rolled)

    @property
    def total(self) -> int:
        return sum(self.rolled)


def cards(facts: Sequence[Fact]) -> tuple[Fact, ...]:
    """The narrator's gate is the player's: an unrevealed entity earns no card of its own."""
    return tuple(fact for fact in facts if fact.told and fact.card)


def traced(facts: Sequence[Fact], *, told_only: bool = False) -> str:
    return "\n".join(f"- {fact.trace}" for fact in facts if fact.told or not told_only) or NOTHING


def roll(faces: Sequence[int], reason: str, rng: Random, *, label: str = "") -> Rolled:
    return _rolled(faces, reason, rng, label, highlight_kept=False)


def roll_pool(faces: Sequence[int], reason: str, rng: Random, *, label: str = "") -> Rolled:
    return _rolled(faces, reason, rng, label, highlight_kept=len(faces) > 1)


def _rolled(
    faces: Sequence[int], reason: str, rng: Random, label: str, *, highlight_kept: bool
) -> Rolled:
    if not faces:
        raise ValueError("a dice pool rolls at least one die")
    drawn = tuple(rng.randint(1, face) for face in faces)
    highlight = (drawn.index(max(drawn)),) if highlight_kept else ()
    notation = _notation(faces)
    event = DiceEvent(
        label=label or notation, faces=tuple(faces), rolled=drawn, highlight=highlight
    )
    shown = ", ".join(str(die) for die in drawn)
    fact = Fact(trace=f"{reason}: {notation} [{shown}]")
    return Rolled(rolled=drawn, event=event, fact=fact)


def _notation(faces: Sequence[int]) -> str:
    if len(faces) == 1:
        return f"d{faces[0]}"
    if len(set(faces)) == 1:
        return f"{len(faces)}d{faces[0]}"
    return "+".join(f"d{face}" for face in faces)
