from collections.abc import Sequence
from random import Random
from typing import Self

from pydantic import model_validator

from aidm.core.entities import Frozen

NOTHING = "- (nothing changed)"
DICE = "dice_rolled"


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

    kind: str
    trace: str
    told: bool = False
    card: str = ""
    dice: tuple[DiceEvent, ...] = ()


def cards(facts: Sequence[Fact]) -> tuple[Fact, ...]:
    """The narrator's gate is the player's: an unrevealed entity earns no card of its own."""
    return tuple(fact for fact in facts if fact.told and fact.card)


def traced(facts: Sequence[Fact], *, told_only: bool = False) -> str:
    """One bullet per fact: how every surface that reports what landed renders it."""
    return "\n".join(f"- {fact.trace}" for fact in facts if fact.told or not told_only) or NOTHING


def roll(faces: Sequence[int], reason: str, rng: Random) -> tuple[tuple[int, ...], Fact]:
    if not faces:
        raise ValueError("a dice pool rolls at least one die")
    drawn = tuple(rng.randint(1, face) for face in faces)
    shown = ", ".join(str(die) for die in drawn)
    return drawn, Fact(kind=DICE, trace=f"{reason}: {_notation(faces)} [{shown}]")


def _notation(faces: Sequence[int]) -> str:
    if len(set(faces)) == 1:
        return f"{len(faces)}d{faces[0]}"
    return "+".join(f"d{face}" for face in faces)
