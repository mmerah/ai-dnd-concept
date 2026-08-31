from collections.abc import Callable, Sequence
from copy import deepcopy
from typing import Self

from pydantic import Field, ValidationError, model_validator

from aidm.engines.loner3e.state import (
    Loner3eCharacter,
    Loner3eScenario,
    Loner3eState,
    LonerScene,
    LonerWorld,
)
from aidm.state.entities import EngineId, Frozen, Mutable, Slug, require_unique
from aidm.state.facts import Fact, cards
from aidm.state.play import Exchange, PendingDecision, SpokenLine

# Phase 6 turns each of these into `Annotated[A | B, Field(discriminator="engine")]`.
Payload = Loner3eState
ScenarioPayload = Loner3eScenario
CharacterPayload = Loner3eCharacter
SceneWrite = LonerScene


class ScenarioMeta(Frozen):
    title: str
    premise: str


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
    history: tuple[Exchange, ...] = ()
    turn_facts: tuple[Fact, ...] = ()
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

    def record(
        self,
        scene_label: str,
        prompt: str,
        lines: tuple[SpokenLine, ...],
        facts: Sequence[Fact],
    ) -> None:
        """The one shape an exchange takes, whether a turn or the player's own action wrote it."""
        self.turn_facts = ()
        self.history = (
            *self.history,
            Exchange(
                prompt=prompt,
                scene=scene_label,
                lines=lines,
                facts=cards(facts),
                decision="" if self.pending is None else self.pending.prompt,
            ),
        )

    def draft(self) -> Self:
        """A working copy a resolution mutates; a failed turn never replaces the committed state."""
        return deepcopy(self)

    def committed(self) -> Self:
        """Dumping runs no validator, so the dump is validated back: that is the commit gate."""
        return type(self).model_validate(self.model_dump(round_trip=True))


def draft_refusal(
    state: Game, mutate: Callable[[Game], object], what: str = "the state this leaves"
) -> str | None:
    draft = state.draft()
    try:
        _ = mutate(draft)
        _ = draft.committed()
    except ValidationError as broken:
        return f"{what} is invalid: {broken.errors()[0]['msg']}"
    except ValueError as refused:
        return str(refused)
    return None
