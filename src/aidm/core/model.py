from collections.abc import Callable
from copy import deepcopy
from typing import Any, Protocol, Self

from pydantic import BaseModel, Field, model_validator

from aidm.core.entities import (
    EngineId,
    Frozen,
    Loose,
    Mutable,
    Refusal,
    Slug,
    parse,
    require_unique,
)
from aidm.core.play import PendingDecision

type AnyScenario = Scenario[Any]
type AnyCharacter = Character[Any]
type AnyGame = Game[Any]
# What `ask` asks of the value it parsed, beyond its own schema; the reason re-prompts.
type Check[T] = Callable[[T], str | None]


class ScenarioMeta(Frozen):
    title: str
    premise: str
    scope: str = Field(
        min_length=1,
        description="How far this adventure reaches, how its consequences develop, and whether "
        "it tends toward an ending or toward continuing concerns; guidance, not a rule.",
    )
    art_style: str = ""  # empty: the engine's own
    voice: str = ""  # empty: the settings' narrator voice

    def with_premise(self, fallback: str) -> Self:
        """The opening's own words stand in for a premise the player never wrote."""
        return self.model_copy(update={"premise": self.premise or fallback})


class EngineHeader(Loose):
    """Routes a document before its engine is known; the rest of the document is ignored."""

    engine: EngineId


class Named(Loose):
    """What every sheet shows the launcher: who this is, in a name and a line."""

    name: str
    brief: str = ""


class CharacterHeader(EngineHeader):
    id: Slug
    payload: Named


class Scenario[P: BaseModel](Frozen):
    """`scenarios/<id>/world.json`: its dump is the scenario envelope around one payload."""

    meta: ScenarioMeta
    engine: EngineId
    packs: tuple[Slug, ...] = ()
    payload: P

    @model_validator(mode="after")
    def _unique_packs(self) -> Self:
        require_unique("scenario pack ids", self.packs)
        return self


class Character[P: BaseModel](Frozen):
    """`characters/<id>/<engine>.json`: the envelope around the sheet this engine plays them by."""

    id: Slug
    engine: EngineId
    payload: P


class WorldsmithAnswer(Protocol):
    async def __call__[M: BaseModel](self, prompt: str, model: type[M], refusal: Check[M]) -> M: ...


class Game[P: BaseModel](Mutable):
    """The game as it is played; its dump is the save envelope around one engine payload."""

    scenario_id: Slug
    character_id: Slug
    scenario: ScenarioMeta
    engine: EngineId
    packs: tuple[Slug, ...] = ()
    pending: PendingDecision | None = None
    # A tool's brief for the worldsmith; the platform writes it once the turn ends, then clears it.
    handoff: str = ""
    notes: list[str] = []
    payload: P

    @model_validator(mode="after")
    def _playable_game(self) -> Self:
        require_unique("game pack ids", self.packs)
        return self

    def note(self, text: str) -> None:
        self.notes.append(text)

    def draft(self) -> Self:
        """A working copy a resolution mutates; a failed turn never replaces the committed state."""
        return deepcopy(self)

    def commit(self) -> Self:
        """The commit gate: the draft revalidated whole; a state the rules refuse never lands."""
        try:
            return parse(type(self), self)
        except Refusal as refused:
            raise Refusal(f"the state this leaves is invalid: {refused}") from refused
