from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import Any

from pydantic import BaseModel

from aidm.core.creation import CreationStep, Picks
from aidm.core.entities import Counter, EngineId, EntityId, Slug, pool, require_unique
from aidm.core.facts import DiceEvent, Fact, roll
from aidm.core.io import ENCODING, decoded
from aidm.core.model import (
    AnyCharacter,
    AnyScenario,
    CheckAnswer,
    EngineHeader,
    Game,
    WorldsmithAnswer,
)
from aidm.core.play import DecisionOption, Exchange, PendingOption, SpokenLine
from aidm.core.tools import MasterTool, Validate
from aidm.core.views import NarratorView, PlayerView, Rows
from aidm.kits.entities import Entity, entity_fact, labeled


@dataclass(frozen=True, slots=True, kw_only=True)
class Authoring:
    answer: type[BaseModel]
    prompt: Callable[[str, str], str]
    refusal: CheckAnswer
    build: Callable[[str, str, tuple[Slug, ...], BaseModel, str], AnyScenario]


@dataclass(frozen=True, slots=True, kw_only=True)
class Transition[G: Game[Any]]:
    """A kit's way of growing the world: when it is offered, how it is written, how it installs."""

    ready: Callable[[G], bool]
    write: Callable[[G, str, str, WorldsmithAnswer], Awaitable[BaseModel]]
    install: Callable[[G, BaseModel], tuple[Fact, ...]]
    # The narrator's brief for the arrival, supplied by the kit whose transition moves the player.
    arrival_brief: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class Engine[G: Game[Any]]:
    """The one extension point joining an engine's rules to its chosen world kit."""

    id: EngineId
    title: str
    instructions: str
    packs: tuple[DecisionOption, ...]
    game: type[G]
    scenario: type[AnyScenario]
    character: type[AnyCharacter]
    guidance: Callable[[Sequence[Slug]], str]
    world_tools: tuple[MasterTool[G], ...]
    tools: tuple[MasterTool[G], ...]
    creation_steps: Callable[[Picks], tuple[CreationStep, ...]]
    create_character: Callable[[str, str, Picks], AnyCharacter]
    preview_character: Callable[[AnyCharacter], Rows]
    validate: Validate[G]
    new_game: Callable[[AnyScenario, AnyCharacter], BaseModel]
    entity_known: Callable[[G, EntityId], bool | None]
    record: Callable[[G, str, tuple[SpokenLine, ...], Sequence[Fact]], tuple[str, ...]]
    history: Callable[[G], tuple[Exchange, ...]]
    master_sections: Callable[[G], Rows]
    narrator_view: Callable[[G], NarratorView]
    player_view: Callable[[G], PlayerView]
    over: Callable[[G], str | None]
    authoring: Authoring
    crossing: Transition[G] | None
    extension: Transition[G] | None

    def __post_init__(self) -> None:
        tools = (*self.world_tools, *self.tools)
        require_unique(f"tool names of the {self.id!r} engine", (one.name for one in tools))

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


def adjust[S: BaseModel](
    player_id: EntityId,
    entity: Entity[S],
    key: str,
    counter: Counter,
    amount: int,
    why: str,
) -> list[Fact]:
    before = counter.current
    counter.current = counter.clamped(before + amount)
    landed = counter.current - before
    if landed == 0:
        return []
    return [_counter_fact(player_id, entity, key, counter, landed, why)]


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


def _counter_fact[S: BaseModel](
    player_id: EntityId,
    entity: Entity[S],
    key: str,
    counter: Counter,
    delta: int,
    why: str,
) -> Fact:
    moved = f"{key.capitalize()} {delta:+d} -> {pool(counter)}"
    card = moved if entity.id == player_id else f"{entity.name}: {moved}"
    trace = f"{labeled(entity, player_id)} {key} {delta:+d} -> {pool(counter)}"
    return entity_fact(entity, "counter_changed", f"{trace} ({why})", card=card)
