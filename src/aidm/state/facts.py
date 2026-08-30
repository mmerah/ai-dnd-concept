from collections.abc import Sequence
from random import Random
from typing import Self

from pydantic import model_validator

from aidm.state.entities import Entity, EntityId, Frozen, kind_word

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

    kind: str
    trace: str
    told: bool = False
    entity_id: EntityId | None = None
    card: str = ""
    dice: tuple[DiceEvent, ...] = ()


def labeled(entity: Entity, player_id: EntityId) -> str:
    """A trace names an entity by kind, name, and exact id, so the Director can reuse the id."""
    word = "player" if entity.id == player_id else kind_word(entity.kind)
    return f"the {word} {entity.name}[{entity.id}]"


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


def cards(facts: Sequence[Fact]) -> tuple[Fact, ...]:
    """The narrator's gate is the player's: an unrevealed entity earns no card of its own."""
    return tuple(fact for fact in facts if fact.told and fact.card)


def traced(facts: Sequence[Fact], *, told_only: bool = False) -> str:
    """One bullet per fact: how every surface that reports what landed renders it."""
    return "\n".join(f"- {fact.trace}" for fact in facts if fact.told or not told_only) or NOTHING


def told_traces(facts: Sequence[Fact]) -> tuple[str, ...]:
    return tuple(fact.trace for fact in facts if fact.told)


def roll(faces: Sequence[int], reason: str, rng: Random) -> tuple[tuple[int, ...], Fact]:
    if not faces:
        raise ValueError("a dice pool rolls at least one die")
    drawn = tuple(rng.randint(1, face) for face in faces)
    shown = ", ".join(str(die) for die in drawn)
    return drawn, Fact(kind="dice_rolled", trace=f"{reason}: {_notation(faces)} [{shown}]")


def _notation(faces: Sequence[int]) -> str:
    if len(set(faces)) == 1:
        return f"{len(faces)}d{faces[0]}"
    return "+".join(f"d{face}" for face in faces)
