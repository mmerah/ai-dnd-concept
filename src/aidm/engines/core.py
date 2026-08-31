from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from random import Random

from pydantic import BaseModel

from aidm.core.creation import CreationStep, Picks
from aidm.core.entities import Counter, EngineId, Slug, pool, require_unique
from aidm.core.facts import DiceEvent, Fact, roll
from aidm.core.io import ENCODING, decoded
from aidm.core.model import Character, EngineHeader, Game, Payload, Scenario
from aidm.core.play import DecisionOption, PendingOption
from aidm.core.tools import MasterTool, Validate
from aidm.core.views import NarratorView, PlayerView, Rows
from aidm.kits.scenes import render
from aidm.kits.scenes.render import EngineSections, SheetRows
from aidm.kits.scenes.state import Entity, entity_fact, labeled


@dataclass(frozen=True, slots=True, kw_only=True)
class Engine:
    """The one engine extension point: one engine ships, so this is concrete, not a protocol."""

    id: EngineId
    title: str
    instructions: str
    packs: tuple[DecisionOption, ...]
    # What a sheet needs for the selected packs, written for the worldsmith.
    guidance: Callable[[Sequence[Slug]], str]
    tools: tuple[MasterTool, ...]
    # Tolerates partial or stale picks, so follow-up steps appear as parents are picked.
    creation_steps: Callable[[Picks], tuple[CreationStep, ...]]
    # Raises ValueError with the reason the page shows when the pick set is illegal.
    create_character: Callable[[str, str, Picks], Character]
    preview_character: Callable[[Character], Rows]
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
        value = decoded(raw)
        if (header := EngineHeader.model_validate(value)).engine != self.id:
            raise ValueError(f"the save plays {header.engine!r}, not {self.id!r}")
        state = Game.model_validate(value)
        self.validate(state)
        return state

    def master_sections(self, state: Game) -> Rows:
        return render.master_sections(state, self.sheet_rows(state), self.sections)

    def narrator_view(self, state: Game) -> NarratorView:
        return render.narrator_view(state.world)

    def player_view(self, state: Game) -> PlayerView:
        return render.player_view(state, self.sheet_rows(state), self.over(state))

    def answer(self, draft: Game, chosen: PendingOption, rng: Random) -> tuple[Fact, ...]:
        found = next((one for one in self.tools if one.name == chosen.name), None)
        if found is None:
            raise ValueError(
                f"the {self.id!r} engine has no tool {chosen.name!r} to play option {chosen.id!r}"
            )
        return found.call(draft, chosen.args, rng)


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
    state: Game, entity: Entity[S], key: str, counter: Counter, delta: int, why: str
) -> Fact:
    moved = f"{key.capitalize()} {delta:+d} -> {pool(counter)}"
    card = moved if entity.id == state.world.player_id else f"{entity.name}: {moved}"
    trace = f"{labeled(entity, state.world.player_id)} {key} {delta:+d} -> {pool(counter)}"
    return entity_fact(entity, "counter_changed", f"{trace} ({why})", card=card)
