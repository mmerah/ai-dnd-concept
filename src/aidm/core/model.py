from collections.abc import Awaitable, Callable
from copy import deepcopy
from typing import Any, Self

from pydantic import BaseModel, Field, SerializeAsAny, model_validator

from aidm.core.entities import EngineId, Frozen, Header, Mutable, Slug, require_unique
from aidm.core.play import PendingDecision


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


class Scenario[P: BaseModel](Frozen):
    """`scenarios/<id>/world.json`: its dump is the scenario envelope around one payload."""

    meta: ScenarioMeta
    engine: EngineId
    packs: tuple[Slug, ...] = ()
    art_style: str = ""
    payload: P

    @model_validator(mode="after")
    def _unique_packs(self) -> Self:
        require_unique("scenario pack ids", self.packs)
        return self


class Character[P: BaseModel](Frozen):
    """`characters/<id>/<engine>.json`: who they are and the payload this engine plays them by."""

    id: Slug
    engine: EngineId
    name: str
    brief: str
    payload: P


class Game[P: BaseModel](Mutable):
    """The game as it is played; its dump is the save envelope around one engine payload."""

    scenario_id: Slug
    character_id: Slug
    scenario: ScenarioMeta
    engine: EngineId
    packs: tuple[Slug, ...] = ()
    turn: int = Field(default=0, ge=0)
    pending: PendingDecision | None = None
    notes: tuple[str, ...] = ()
    payload: SerializeAsAny[P]

    @model_validator(mode="after")
    def _playable_game(self) -> Self:
        require_unique("game pack ids", self.packs)
        return self

    def take_notes(self) -> tuple[str, ...]:
        """Notes are read once; a note a tool writes after this steers the next turn."""
        notes, self.notes = self.notes, ()
        return notes

    def draft(self) -> Self:
        """A working copy a resolution mutates; a failed turn never replaces the committed state."""
        return deepcopy(self)

    def committed(self) -> Self:
        """Dumping runs no validator, so the dump is validated back: that is the commit gate."""
        return type(self).model_validate(self.model_dump(round_trip=True))


type CheckAnswer = Callable[[BaseModel], str | None]
type WorldsmithAnswer = Callable[[str, type[BaseModel], CheckAnswer], Awaitable[BaseModel]]


type AnyScenario = Scenario[Any]
type AnyCharacter = Character[Any]
type AnyGame = Game[Any]
