from collections.abc import Callable
from copy import deepcopy
from typing import Any, Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, SerializeAsAny, model_validator

from aidm.core.entities import EngineId, Frozen, Mutable, Slug, require_unique
from aidm.core.play import PendingDecision

type ScenarioKind = Literal["one-shot", "campaign"]
type AnyScenario = Scenario[Any]
type AnyCharacter = Character[Any]
type AnyGame = Game[Any]


class ScenarioMeta(Frozen):
    title: str
    premise: str
    kind: ScenarioKind = "one-shot"


class EngineHeader(BaseModel):
    """Routes a document before its engine is known; the rest of the document is ignored."""

    model_config = ConfigDict(extra="ignore", frozen=True)

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


class WorldsmithAnswer(Protocol):
    """How an engine asks the worldsmith: one prompt, the model to answer in, one refusal."""

    async def __call__[M: BaseModel](
        self, prompt: str, model: type[M], refusal: Callable[[M], str | None]
    ) -> M: ...


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

    def draft(self) -> Self:
        """A working copy a resolution mutates; a failed turn never replaces the committed state."""
        return deepcopy(self)

    def committed(self) -> Self:
        """Dumping runs no validator, so the dump is validated back: that is the commit gate."""
        return type(self).model_validate(self.model_dump(round_trip=True))
