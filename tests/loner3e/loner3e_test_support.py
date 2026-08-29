from pathlib import Path
from random import Random

from core_test_support import ENGINES_BUILT, LONER3E, character, offline_settings, scenario

from aidm.app.runtime import GameSession, LaunchTarget
from aidm.content.io import FileStore
from aidm.engines.core import load_packs, mechanics_of
from aidm.engines.loner3e.engine import ENGINE_DIR, complete_chapter
from aidm.engines.loner3e.rules import SRD_PACK, Loner3eState, Pack, Sheet, twist_table
from aidm.state.entities import EntityId
from aidm.state.model import Game
from aidm.turn.run import build_turn_agents

TARGET = LaunchTarget(slug="poc", scenario_id="whispering-vault", character_id="kael")
TWISTS = twist_table(load_packs((ENGINE_DIR / "packs",), Pack), SRD_PACK)


def loner3e_session(directory: Path) -> GameSession:
    settings = offline_settings()
    engine = ENGINES_BUILT[LONER3E]
    return GameSession(
        target=TARGET,
        scenario=scenario(),
        character=character(),
        engine=engine,
        stages=build_turn_agents(engine, settings),
        store=FileStore(directory),
        settings=settings,
        rng=Random(1),
    )


def sheet(state: Game, entity_id: EntityId) -> Sheet:
    """One sheet out of the blob: a copy, so changing state needs `rules()`."""
    return mechanics_of(state.world, Loner3eState).sheets[entity_id]


def at_boundary(state: Game) -> Game:
    """One chapter recorded — the adventure ended — for everyone who played it."""
    draft = state.draft()
    _ = complete_chapter(draft)
    return draft.committed()
