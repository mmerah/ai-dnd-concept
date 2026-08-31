from collections.abc import Sequence
from copy import deepcopy
from typing import Self

from pydantic import Field, model_validator

from aidm.core.entities import EngineId, Frozen, Header, Mutable, Slug, require_unique
from aidm.core.facts import Fact, cards
from aidm.core.play import Exchange, PendingDecision, SpokenLine
from aidm.engines.loner3e.state import (
    Loner3eCharacter,
    Loner3eScenario,
    Loner3eState,
    LonerScene,
    LonerWorld,
)

Payload = Loner3eState
ScenarioPayload = Loner3eScenario
CharacterPayload = Loner3eCharacter
SceneWrite = LonerScene


class ScenarioMeta(Frozen):
    title: str
    premise: str


class EngineHeader(Header):
    engine: EngineId


class SaveHeader(EngineHeader):
    scenario_id: Slug
    character_id: Slug
    scenario: ScenarioMeta
    turn: int = Field(ge=0)


class CharacterHeader(EngineHeader):
    id: Slug
    name: str


class Scenario(Frozen):
    """`scenarios/<id>/world.json`: its dump is the scenario envelope around one payload."""

    meta: ScenarioMeta
    engine: EngineId
    packs: tuple[Slug, ...] = Field(min_length=1)
    art_style: str = ""
    payload: ScenarioPayload

    @model_validator(mode="after")
    def _unique_packs(self) -> Self:
        require_unique("scenario pack ids", self.packs)
        return self


class Character(Frozen):
    """`characters/<id>/<engine>.json`: who they are and the payload this engine plays them by."""

    id: Slug
    engine: EngineId
    name: str
    brief: str
    payload: CharacterPayload


class Game(Mutable):
    """The game as it is played; its dump is the save envelope around one engine payload."""

    scenario_id: Slug
    character_id: Slug
    scenario: ScenarioMeta
    engine: EngineId
    packs: tuple[Slug, ...] = Field(min_length=1)
    turn: int = Field(default=0, ge=0)
    pending: PendingDecision | None = None
    notes: tuple[str, ...] = ()
    payload: Payload

    @model_validator(mode="after")
    def _playable_game(self) -> Self:
        require_unique("game pack ids", self.packs)
        if self.engine != self.payload.engine:
            raise ValueError(f"a {self.engine!r} save carries a {self.payload.engine!r} payload")
        return self

    @property
    def world(self) -> LonerWorld:
        return self.payload.world

    def take_notes(self) -> tuple[str, ...]:
        """Notes are read once; a note a tool writes after this steers the next turn."""
        notes, self.notes = self.notes, ()
        return notes

    def record(self, prompt: str, lines: tuple[SpokenLine, ...], facts: Sequence[Fact]) -> None:
        self.world.run.exchanges.append(
            Exchange(
                prompt=prompt,
                lines=lines,
                facts=cards(facts),
                decision="" if self.pending is None else self.pending.prompt,
            )
        )

    def draft(self) -> Self:
        """A working copy a resolution mutates; a failed turn never replaces the committed state."""
        return deepcopy(self)

    def committed(self) -> Self:
        """Dumping runs no validator, so the dump is validated back: that is the commit gate."""
        return type(self).model_validate(self.model_dump(round_trip=True))
