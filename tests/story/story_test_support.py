from pathlib import Path
from random import Random

from core_test_support import STORY, character, game, scenario, settings

from aidm.app.session import GameSession, LaunchTarget, build_engine
from aidm.content.store import FileSaves, FileTraces
from aidm.engines.loader import Engine
from aidm.engines.story.advance import GROWTH_REQUIRED
from aidm.state.world import GameState, player_sheet
from aidm.turn.advancement import advisor
from aidm.turn.pipeline import TurnOptions, build_stages

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
        stages=build_stages(engine, config),
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
