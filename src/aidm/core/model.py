from collections.abc import Callable
from copy import deepcopy
from typing import Any, Protocol, Self

from pydantic import BaseModel, Field

from aidm.core.entities import EngineId, Frozen, Loose, Mutable, Refusal, Slug, parse
from aidm.core.play import Chapter, Exchange, PendingDecision

type AnyScenario = Scenario[Any]
type AnyCharacter = Character[Any]
type AnyGame = Game[Any]
# An extra check on a parsed value; it raises the reason to ask the model again.
type Check[T] = Callable[[T], None]


class ScenarioMeta(Frozen):
    title: str
    premise: str
    scope: str = Field(min_length=1)
    art_style: str = ""  # empty: the engine's own
    voice: str = ""  # empty: the settings' narrator voice

    def check_drift(self, other: Self) -> None:
        """One rule, so the launcher and the game page never disagree about a stale save."""
        fields = ScenarioMeta.model_fields
        if drifted := [name for name in fields if getattr(self, name) != getattr(other, name)]:
            raise Refusal(f"save scenario differs from the one on disk in: {', '.join(drifted)}")


class EngineHeader(Loose):
    engine: EngineId


class SheetHeader(Loose):
    name: str
    brief: str = ""


class CharacterHeader(EngineHeader):
    id: Slug
    sheet: SheetHeader


class Scenario[O: BaseModel](Frozen):
    meta: ScenarioMeta
    engine: EngineId
    pack_id: Slug
    source: str = ""
    opening: O


class Character[S: BaseModel](Frozen):
    id: Slug
    engine: EngineId
    sheet: S


class WorldsmithAnswer(Protocol):
    async def __call__[M: BaseModel](
        self, prompt: str, model: type[M], check: Check[M], /
    ) -> M: ...


class Commission(Frozen):
    """An engine's one request to the worldsmith; the platform runs it once the turn ends."""

    operation: Slug  # the engine's own name for what it will author and install
    detail: str = Field(min_length=1)
    target: Slug | None = None


class Game[W: BaseModel](Mutable):
    scenario_id: Slug
    character_id: Slug
    scenario: ScenarioMeta
    engine: EngineId
    pack_id: Slug
    source: str = ""
    pending: PendingDecision | None = None
    # `exclude=True` keeps it out of every save, so `restore` only refuses a hand-edited one.
    commission: Commission | None = Field(default=None, exclude=True)
    notes: list[str] = Field(default_factory=list)
    log: list[Chapter] = Field(default_factory=list)
    world: W

    def note(self, text: str) -> None:
        self.notes.append(text)

    def exchanges(self) -> tuple[Exchange, ...]:
        return tuple(exchange for chapter in self.log for exchange in chapter.exchanges)

    def draft(self) -> Self:
        """A working copy a resolution mutates; a failed turn never replaces the committed state."""
        return deepcopy(self)

    def commit(self) -> Self:
        try:
            return parse(type(self), self)
        except Refusal as refused:
            raise Refusal(f"the state this leaves is invalid: {refused}") from refused
