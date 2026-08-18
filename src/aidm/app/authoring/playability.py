from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from aidm.config import Settings
from aidm.content.authored import Character, Scenario, ScenarioOverlay, ScenarioWorld
from aidm.content.store import engine_text, load_character
from aidm.engines.engine import Engine
from aidm.engines.registry import engine_ids
from aidm.engines.sheets import SheetBase
from aidm.state.base import Slug
from aidm.state.effects import AdvanceThread
from aidm.state.world import CONNECTED, LOCKED_TAG, Hook

from ..session import begin_game, build_engine
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

    def check(self, slug: Slug, world: ScenarioWorld, overlay: ScenarioOverlay) -> None:
        scenario = Scenario(id=slug, engine=self.engine.id, world=world, overlay=overlay)
        self.engine.check_overlay(overlay.entities.values())
        _ = begin_game(self.engine, scenario, self.character)


def playtests(config: Settings) -> tuple[Playtest, ...]:
    built: list[Playtest] = []
    for engine_id in engine_ids():
        engine = build_engine(engine_id)
        character = load_character(config.characters_dir, STARTER, engine.binding())
        built.append(Playtest(engine=engine, character=character))
    return tuple(built)


def _advances_on_discovery(hook: Hook) -> bool:
    return hook.match.kind == "entity_discovered" and any(
        isinstance(effect, AdvanceThread) for effect in hook.effects
    )


def _bar_unmet(world: ScenarioWorld) -> list[str]:
    """The bar the instructions set, checked mechanically — every unmet item found at once."""
    unmet: list[str] = []
    locations = sorted(entity.id for entity in world.entities if entity.kind == "location")
    if len(locations) < 4:
        unmet.append(f"four or more locations; the draft has {len(locations)}: {locations}")
    ways = [relation for relation in world.relations if relation.kind == CONNECTED]
    if all(way.known for way in ways):
        unmet.append("at least one `connected` relation starting `known: false` — a way to find")
    if not any(LOCKED_TAG in way.tags for way in ways):
        unmet.append(f"at least one `connected` relation tagged {LOCKED_TAG!r}")
    actors = [entity for entity in world.entities if entity.kind == "actor"]
    if len(actors) < 2:
        actor_ids = sorted(actor.id for actor in actors)
        unmet.append(f"two or more actors; the draft has {len(actors)}: {actor_ids}")
    if all(actor.known for actor in actors):
        unmet.append("at least one actor starting `known: false`")
    if not any(entity.kind == "item" and not entity.known for entity in world.entities):
        unmet.append("at least one item starting `known: false` — a secret to find")
    if not world.threads:
        unmet.append("at least one thread")
    if not any(_advances_on_discovery(hook) for hook in world.hooks):
        unmet.append("at least one hook that advances a thread on an `entity_discovered` fact")
    return unmet


def _opening_unmet(world: ScenarioWorld) -> list[str]:
    """An opening slice's bar: what the first scene needs, since the rest materializes in play."""
    unmet: list[str] = []
    beyond = [entity for entity in world.entities if entity.id != world.starting_location_id]
    if len(beyond) < 2:
        unmet.append(
            f"two or three entities besides the starting location; the draft has {len(beyond)}"
        )
    if not world.threads:
        unmet.append("at least one thread")
    return unmet


@dataclass(frozen=True, slots=True)
class Brief:
    """How much world one run authors: the instructions it works from and the bar it is held to."""

    instructions: str
    unmet: Callable[[ScenarioWorld], list[str]]


FULL = Brief(_instructions("scenario_bar.md"), _bar_unmet)
# An opening slice is deliberately thin: the rest of the world is written during play.
OPENING = Brief(_instructions("scenario_opening.md"), _opening_unmet)


def playability(
    draft: WorldDraft, slug: Slug, playing: Sequence[Playtest], brief: Brief = FULL
) -> str | None:
    """The exact reason the draft will not play, or None; ValidationError counts as ValueError."""
    try:
        world = draft.world()
        for playtest in playing:
            playtest.check(slug, world, ScenarioOverlay())
    except ValueError as refused:
        return str(refused)
    if unmet := brief.unmet(world):
        listed = "\n".join(f"- {item}" for item in unmet)
        return f"the draft plays, but it is under the bar. Still missing:\n{listed}"
    return None
