from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from aidm.app.registry import begin_game, build_engine
from aidm.config import Settings
from aidm.content.authored import Character, Scenario
from aidm.content.store import engine_text, load_character
from aidm.engines.engine import Engine
from aidm.engines.sheets import SheetBase
from aidm.state.base import EngineId

from .draft import WorldDraft

# Every generated scenario must be playable by the character the app ships with.
STARTER = "kael"

_PROMPTS_DIR = Path(__file__).parents[1] / "prompts"
_BASE_INSTRUCTIONS = engine_text(_PROMPTS_DIR / "scenario_world.md")


def _instructions(bar: str) -> str:
    return f"{_BASE_INSTRUCTIONS}\n\n{engine_text(_PROMPTS_DIR / bar)}"


@dataclass(frozen=True, slots=True)
class Playtest:
    engine: Engine[SheetBase]
    character: Character

    def check(self, scenario: Scenario) -> None:
        # A playtest never saves, so the game's id is never read; any well-formed slug serves.
        _ = begin_game(self.engine, "draft", scenario, self.character)


def playtests(config: Settings, engines: Sequence[EngineId]) -> tuple[Playtest, ...]:
    built: list[Playtest] = []
    for engine_id in engines:
        engine = build_engine(engine_id)
        character = load_character(config.characters_dir, STARTER, engine.id, engine.check_overlay)
        built.append(Playtest(engine=engine, character=character))
    return tuple(built)


def _bar_unmet(scenario: Scenario) -> list[str]:
    """The bar the instructions set, checked mechanically — every unmet item found at once."""
    unmet: list[str] = []
    entities, threads = scenario.world.entities, scenario.world.threads
    locations = sorted(entity.id for entity in entities if entity.kind == "location")
    if len(locations) < 4:
        unmet.append(f"four or more locations; the draft has {len(locations)}: {locations}")
    ways = [way for entity in entities for way in entity.exits]
    if all(way.known for way in ways):
        unmet.append("at least one exit starting `known: false` — a way to find")
    if not any(way.locked for way in ways):
        unmet.append("at least one exit starting `locked: true`")
    actors = [entity for entity in entities if entity.kind == "actor"]
    if len(actors) < 2:
        actor_ids = sorted(actor.id for actor in actors)
        unmet.append(f"two or more actors; the draft has {len(actors)}: {actor_ids}")
    if all(actor.known for actor in actors):
        unmet.append("at least one actor starting `known: false`")
    if not any(entity.kind == "item" and not entity.known for entity in entities):
        unmet.append("at least one item starting `known: false` — a secret to find")
    if not threads:
        unmet.append("at least one thread")
    if not any(
        entity.detail is not None and entity.detail.when_reached and not entity.known
        for entity in entities
    ):
        unmet.append(
            "at least one unknown entity whose `detail.when_reached` carries a consequence"
        )
    return unmet


def _opening_unmet(scenario: Scenario) -> list[str]:
    """An opening slice's bar: what the first scene needs, since the rest materializes in play."""
    unmet: list[str] = []
    beyond = [
        entity for entity in scenario.world.entities if entity.id != scenario.starting_location_id
    ]
    if len(beyond) < 2:
        unmet.append(
            f"two or three entities besides the starting location; the draft has {len(beyond)}"
        )
    if not scenario.world.threads:
        unmet.append("at least one thread")
    return unmet


@dataclass(frozen=True, slots=True)
class Brief:
    """How much world one run authors: the instructions it works from and the bar it is held to."""

    instructions: str
    unmet: Callable[[Scenario], list[str]]


FULL = Brief(_instructions("scenario_bar.md"), _bar_unmet)
# An opening slice is deliberately thin: the rest of the world is written during play.
OPENING = Brief(_instructions("scenario_opening.md"), _opening_unmet)


def playability(draft: WorldDraft, playing: Sequence[Playtest], brief: Brief = FULL) -> str | None:
    """The exact reason the draft will not play, or None; ValidationError counts as ValueError."""
    try:
        scenario = draft.scenario(tuple(playtest.engine.id for playtest in playing))
        for playtest in playing:
            playtest.check(scenario)
    except ValueError as refused:
        return str(refused)
    if unmet := brief.unmet(scenario):
        listed = "\n".join(f"- {item}" for item in unmet)
        return f"the draft plays, but it is under the bar. Still missing:\n{listed}"
    return None
