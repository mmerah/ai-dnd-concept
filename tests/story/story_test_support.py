from pathlib import Path
from random import Random

from core_test_support import STORY, character, game, scenario, settings

from aidm.core.engine import Engine
from aidm.core.registry import build_engine
from aidm.core.store import FileSaves, FileTraces
from aidm.core.world import GameState, player_sheet
from aidm.engines.story.advance import GROWTH_REQUIRED
from aidm.workflow.pipeline import TurnOptions, default_cast
from aidm.workflow.proposals import advisor
from aidm.workflow.session import GameSession, LaunchTarget

TARGET = LaunchTarget(
    slug="poc",
    scenario_id="whispering-vault",
    character_id="kael",
    engine=STORY,
)
OPTIONS = TurnOptions(history_window=6, max_growth=3)


def story_game() -> tuple[Engine, GameState]:
    return game(STORY)


def story_session(directory: Path, rng: Random | None = None) -> GameSession:
    config = settings()
    engine = build_engine(STORY, config)
    return GameSession(
        target=TARGET,
        scenario=scenario(),
        character=character(),
        engine=engine,
        script=default_cast(engine, config).script(engine, OPTIONS),
        advisor=advisor(engine, config),
        saves=FileSaves(directory),
        traces=FileTraces(directory),
        options=OPTIONS,
        rng=Random(1) if rng is None else rng,
    )


def grown(state: GameState) -> GameState:
    """The state a run of player setbacks leaves behind: growth full, advancement on offer."""
    draft = state.draft()
    player_sheet(draft).counters["growth"].current = GROWTH_REQUIRED
    return draft.committed()
