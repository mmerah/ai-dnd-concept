from collections.abc import Sequence
from typing import Self

from pydantic import model_validator

from aidm.state.entities import Entity, EntityId, Frozen, kind_word

NOTHING_MECHANICAL = "- (nothing mechanical happened)"
NOTHING_CHANGED = "- (nothing changed)"


class EventBadge(Frozen):
    label: str
    value: str


class DiceEvent(Frozen):
    label: str
    faces: tuple[int, ...]
    rolled: tuple[int, ...]
    kept: int

    @model_validator(mode="after")
    def _rolled_matches_faces(self) -> Self:
        if len(self.rolled) != len(self.faces):
            raise ValueError("one rolled value per face")
        for die, face in zip(self.rolled, self.faces, strict=True):
            if not 1 <= die <= face:
                raise ValueError(f"a d{face} cannot show {die}")
        if self.kept not in self.rolled:
            raise ValueError("the kept die must be among those rolled")
        return self


class MechanicEvent(Frozen):
    """Player-facing: no field for model-authored free text, so a canon leak has no channel."""

    title: str
    badges: tuple[EventBadge, ...] = ()
    dice: tuple[DiceEvent, ...] = ()
    outcome: str = ""
    effects: tuple[str, ...] = ()
    icon: str = "casino"


class Fact(Frozen):
    """One thing that occurred, rendered where its values were in scope."""

    kind: str
    trace: str
    told: bool = False
    entity_id: EntityId | None = None
    event: MechanicEvent | None = None


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
    event: MechanicEvent | None = None,
) -> Fact:
    """An entity the player has not learned of narrates nothing, so no unknown name leaks."""
    return Fact(
        kind=kind,
        trace=trace,
        told=narrate and entity.known,
        entity_id=entity.id,
        event=event,
    )


def explained_fact(
    entity: Entity,
    kind: str,
    trace: str,
    why: str,
    *,
    event: MechanicEvent | None = None,
) -> Fact:
    rendered = f"{trace} ({why})" if why else trace
    return entity_fact(entity, kind, rendered, event=event)


def player_events(facts: Sequence[Fact]) -> tuple[MechanicEvent, ...]:
    """The narrator's gate is the player's: an unrevealed entity earns no card of its own."""
    return tuple(fact.event for fact in facts if fact.event is not None and fact.told)


def trace_lines(facts: Sequence[Fact]) -> list[str]:
    """One bullet per fact: how every surface that reports what landed renders it."""
    return [f"- {fact.trace}" for fact in facts]


def traced(facts: Sequence[Fact], empty: str = NOTHING_CHANGED) -> str:
    return "\n".join(trace_lines(facts)) or empty


def narrator_lines(facts: Sequence[Fact]) -> tuple[str, ...]:
    return tuple(fact.trace for fact in facts if fact.told)


def narrator_evidence(facts: Sequence[Fact]) -> str:
    return "\n".join(f"- {told}" for told in narrator_lines(facts)) or NOTHING_MECHANICAL
