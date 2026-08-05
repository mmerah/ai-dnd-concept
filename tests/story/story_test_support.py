from pathlib import Path
from random import Random

from core_test_support import STORY, character, scenario, settings

from aidm.core.base import SAVE_VERSION
from aidm.core.content import authored_world
from aidm.core.engine import Engine
from aidm.core.registry import build_engine
from aidm.core.sheet import Sheet, player_sheet
from aidm.core.store import FileSaves, FileTraces
from aidm.core.world import EngineRules, GameState
from aidm.engines.story.advance import GROWTH_REQUIRED
from aidm.engines.story.engine import build_story_engine
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


def story_game() -> tuple[Engine[Sheet], GameState[Sheet]]:
    """Typed to `Sheet`, unlike `core_test_support.initialized`, so a test can read the payload."""
    engine = build_story_engine()
    selected_scenario, selected_character = scenario(), character()
    state = engine.state_type(
        save_version=SAVE_VERSION,
        scenario_id=selected_scenario.id,
        character_id=selected_character.id,
        scenario=selected_scenario.meta,
        engine=engine.id,
        world=engine.initial_world(
            authored_world(selected_scenario, selected_character),
            selected_character.overlay.character,
        ),
    )
    engine.validate_state(state)
    return engine, state


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


def grown[R: EngineRules](state: GameState[R]) -> GameState[R]:
    """The state a run of player setbacks leaves behind: growth full, advancement on offer."""
    draft = state.draft()
    player_sheet(draft).counters["growth"].current = GROWTH_REQUIRED
    return draft.committed()
