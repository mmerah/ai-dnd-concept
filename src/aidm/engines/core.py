from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import Any, Self

from pydantic import BaseModel, model_validator

from aidm.core.creation import CreationStep, Picks
from aidm.core.entities import EngineId, EntityId, Mutable, Slug, require_unique
from aidm.core.facts import DiceEvent, Fact, roll
from aidm.core.io import ENCODING, decoded
from aidm.core.model import (
    AnyCharacter,
    AnyScenario,
    EngineHeader,
    Game,
    WorldsmithAnswer,
)
from aidm.core.play import DecisionOption, Exchange, PendingOption, SpokenLine
from aidm.core.tools import MasterTool, Validate
from aidm.core.views import NarratorView, PlayerView, Rows

PLAYER_ID = EntityId("player")


class Counter(Mutable):
    current: int
    maximum: int

    @model_validator(mode="after")
    def _within_bounds(self) -> Self:
        if self.current < 0:
            raise ValueError(f"{self.current} is below zero")
        if self.current > self.maximum:
            raise ValueError(f"{self.current} is above maximum {self.maximum}")
        return self

    def clamped(self, value: int) -> int:
        return min(max(value, 0), self.maximum)


@dataclass(frozen=True, slots=True, kw_only=True)
class Authoring:
    answer: type[BaseModel]
    prompt: Callable[[str, Sequence[Slug]], str]
    build: Callable[[str, str, str, tuple[Slug, ...], BaseModel, str], AnyScenario]


@dataclass(frozen=True, slots=True, kw_only=True)
class Transition[G: Game[Any]]:
    """How the world grows: when it is offered, how it is written, how it installs."""

    ready: Callable[[G], bool]
    write: Callable[[G, str, WorldsmithAnswer], Awaitable[BaseModel]]
    install: Callable[[G, BaseModel], tuple[Fact, ...]]
    arrival_brief: Callable[[str], str] | None


@dataclass(frozen=True, slots=True, kw_only=True)
class Engine[G: Game[Any]]:
    """The seam joining an engine's rules to the platform."""

    id: EngineId
    title: str
    instructions: str
    packs: tuple[DecisionOption, ...]
    game: type[G]
    scenario: type[AnyScenario]
    character: type[AnyCharacter]
    creation_steps: Callable[[Picks], tuple[CreationStep, ...]]
    create_character: Callable[[str, str, Picks], AnyCharacter]
    preview_character: Callable[[AnyCharacter], Rows]
    tools: tuple[MasterTool[G], ...]
    validate: Validate[G]
    new_game: Callable[[AnyScenario, AnyCharacter], BaseModel]
    over: Callable[[G], str | None]
    known: Callable[[G, EntityId], bool | None]
    record: Callable[[G, str, tuple[SpokenLine, ...], Sequence[Fact]], tuple[str, ...]]
    history: Callable[[G], tuple[Exchange, ...]]
    master_sections: Callable[[G], Rows]
    narrator_view: Callable[[G], NarratorView]
    player_view: Callable[[G], PlayerView]
    authoring: Authoring
    transition: Transition[G]

    def __post_init__(self) -> None:
        require_unique(f"tool names of the {self.id!r} engine", (one.name for one in self.tools))

    def restored(self, raw: str) -> G:
        value = decoded(raw)
        if (header := EngineHeader.model_validate(value)).engine != self.id:
            raise ValueError(f"the save plays {header.engine!r}, not {self.id!r}")
        state = self.game.model_validate(value)
        self.validate(state)
        return state

    def answer(self, draft: G, chosen: PendingOption, rng: Random) -> tuple[Fact, ...]:
        found = next((one for one in self.tools if one.name == chosen.name), None)
        if found is None:
            raise ValueError(
                f"the {self.id!r} engine has no tool {chosen.name!r} to play option {chosen.id!r}"
            )
        return found.call(draft, chosen.args, rng)


type AnyEngine = Engine[Any]


def pool(counter: Counter) -> str:
    return f"{counter.current}/{counter.maximum}"


def keep_highest(
    faces: Sequence[int], reason: str, rng: Random, *, label: str
) -> tuple[int, DiceEvent, Fact]:
    rolled, fact = roll(faces, reason, rng)
    kept = max(rolled)
    event = DiceEvent(
        label=label, faces=tuple(faces), rolled=rolled, highlight=(rolled.index(kept),)
    )
    return kept, event, fact


def load_packs[P: BaseModel](directories: Sequence[Path], model: type[P]) -> dict[str, P]:
    """Later directories win; a broken file raises rather than being skipped."""
    packs: dict[str, P] = {}
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            packs[path.stem] = model.model_validate_json(path.read_text(encoding=ENCODING))
    return packs
