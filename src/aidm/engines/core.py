from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from random import Random

from pydantic import BaseModel

from aidm.content.io import ENCODING
from aidm.kernel.envelope import CharacterEnvelope, SaveEnvelope
from aidm.kernel.views import CreationPreview, Views
from aidm.kits.scenes.state import Entity, entity_fact, labeled
from aidm.kits.scenes.views import (
    EngineSections,
    SheetRows,
    director_view,
    narrator_view,
    player_view,
)
from aidm.state.creation import CreationStep, Picks
from aidm.state.entities import Counter, EngineId, Slug, pool, require_unique
from aidm.state.facts import DiceEvent, Fact, roll
from aidm.state.model import Character, Game, Payload, Scenario
from aidm.state.play import DecisionOption, PendingOption
from aidm.state.tools import DirectorTool, Validate


def _counter_fact[S: BaseModel](
    state: Game, entity: Entity[S], key: str, counter: Counter, delta: int, why: str
) -> Fact:
    moved = f"{key.capitalize()} {delta:+d} -> {pool(counter)}"
    card = moved if entity.id == state.world.player_id else f"{entity.name}: {moved}"
    trace = f"{labeled(entity, state.world.player_id)} {key} {delta:+d} -> {pool(counter)}"
    return entity_fact(entity, "counter_changed", f"{trace} ({why})", card=card)


def adjust[S: BaseModel](
    state: Game, entity: Entity[S], key: str, counter: Counter, amount: int, why: str
) -> list[Fact]:
    before = counter.current
    counter.current = counter.clamped(before + amount)
    landed = counter.current - before
    if landed == 0:
        return []
    return [_counter_fact(state, entity, key, counter, landed, why)]


def keep_highest(
    faces: Sequence[int], reason: str, rng: Random, *, label: str
) -> tuple[int, DiceEvent, Fact]:
    rolled, fact = roll(faces, reason, rng)
    kept = max(rolled)
    event = DiceEvent(
        label=label, faces=tuple(faces), rolled=rolled, highlight=(rolled.index(kept),)
    )
    return kept, event, fact


class CharacterCreation(ABC):
    @abstractmethod
    def steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        """Tolerates partial or stale picks, so follow-up steps appear as parents are picked."""

    @abstractmethod
    def create(self, name: str, brief: str, picks: Picks) -> Character:
        """Raises ValueError with the reason the page shows when the pick set is illegal."""

    @abstractmethod
    def preview(self, character: Character) -> CreationPreview: ...

    def created(
        self, name: str, brief: str, picks: Picks
    ) -> tuple[CharacterEnvelope, CreationPreview]:
        character = self.create(name, brief, picks)
        envelope = CharacterEnvelope(
            id=character.id,
            engine=character.engine,
            name=character.name,
            brief=character.brief,
            payload=character.payload.model_dump(mode="json"),
        )
        return envelope, self.preview(character)


def load_packs[P: BaseModel](directories: Sequence[Path], model: type[P]) -> dict[str, P]:
    """Later directories win; a broken file raises rather than being skipped."""
    packs: dict[str, P] = {}
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            packs[path.stem] = model.model_validate_json(path.read_text(encoding=ENCODING))
    return packs


@dataclass(frozen=True, slots=True, kw_only=True)
class Engine:
    """Satisfies `kernel.protocol.Engine` structurally; one engine ships, so this is concrete."""

    id: EngineId
    title: str
    instructions: str
    packs: tuple[DecisionOption, ...]
    # What a sheet needs for the selected packs, written for the worldsmith.
    guidance: Callable[[Sequence[Slug]], str]
    tools: tuple[DirectorTool, ...]
    creation: CharacterCreation
    validate: Validate
    new_game: Callable[[Scenario, Character], Payload]
    sheet_rows: Callable[[Game], SheetRows]
    sections: EngineSections
    # None while the game can still be played on; the text the player is shown when it cannot.
    over: Callable[[Game], str | None]
    # What the rules settle as a scene ends, such as luck restored after a conflict.
    scene_closed: Callable[[Game], tuple[Fact, ...]]

    def __post_init__(self) -> None:
        require_unique(f"tool names of the {self.id!r} engine", (one.name for one in self.tools))

    def restored(self, raw: str) -> Game:
        envelope = SaveEnvelope.model_validate_json(raw)
        if envelope.engine != self.id:
            raise ValueError(f"the save plays {envelope.engine!r}, not {self.id!r}")
        state = Game.model_validate_json(raw)
        self.validate(state)
        return state

    def views(self, state: Game) -> Views:
        return Views(
            director=director_view(state, self.sheet_rows(state), self.sections),
            narrator=narrator_view(state.world),
            player=player_view(state, self.sheet_rows(state), self.over(state)),
        )

    def answer(self, draft: Game, chosen: PendingOption, rng: Random) -> tuple[Fact, ...]:
        found = next((one for one in self.tools if one.name == chosen.name), None)
        if found is None:
            raise ValueError(
                f"the {self.id!r} engine has no tool {chosen.name!r} to play option {chosen.id!r}"
            )
        return found.call(draft, chosen.args, rng)
