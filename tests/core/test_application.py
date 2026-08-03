from pathlib import Path
from random import Random

import pytest
from core_test_support import character, scenario, settings, updated
from story_test_support import setback_direction

from aidm.agents import director_stage, shared_stages
from aidm.application import GameSession, LaunchTarget, Runtime
from aidm.content import ScenarioMeta
from aidm.engines.dnd5e.advancement import Dnd5eAdvancementDecisions
from aidm.engines.story.access import player_rules
from aidm.engines.story.advancement import RaiseApproach
from aidm.engines.story.engine import build_story_engine
from aidm.pipeline import TurnOptions
from aidm.store import FileSaves, FileTraces
from aidm.turn import Advance

TARGET = LaunchTarget(
    slug="poc",
    scenario_id="whispering-vault",
    character_id="kael",
    engine="story",
)


def session(directory: Path) -> GameSession:
    engine = build_story_engine()
    config = settings()
    return GameSession(
        target=TARGET,
        scenario=scenario(),
        character=character(),
        engine=engine,
        director=director_stage(engine, config),
        stages=shared_stages(config),
        saves=FileSaves(directory),
        traces=FileTraces(directory),
        options=TurnOptions(history_window=6, max_growth=3),
        rng=Random(1),
    )


def test_opening_does_not_save_and_restart_discards_durable_state(tmp_path: Path) -> None:
    saves, traces = FileSaves(tmp_path), FileTraces(tmp_path)
    game = session(tmp_path)
    assert saves.slugs() == ()

    saves.save("poc", updated(game.state, turn=7))
    assert session(tmp_path).state.turn == 7

    game = session(tmp_path)
    game.restart()
    assert game.state.turn == 0
    assert game.entries == []
    assert saves.load("poc") is None
    assert traces.load("poc") == ()


@pytest.mark.parametrize(
    ("change", "message"),
    (
        ({"character_id": "someone-else"}, "save is 'whispering-vault'/'someone-else'"),
        ({"scenario": ScenarioMeta(title="Another Vault", premise="Elsewhere.")}, "Another Vault"),
    ),
    ids=("another origin", "a scenario edited since the save"),
)
def test_resume_refuses_a_save_that_is_not_this_game(
    tmp_path: Path, change: dict[str, object], message: str
) -> None:
    """A save names its own origin by id; the meta comparison catches an edit under a kept id."""
    game = session(tmp_path)
    FileSaves(tmp_path).save("poc", updated(game.state, **change))

    with pytest.raises(ValueError, match=message):
        session(tmp_path)


def test_advancement_commits_through_the_same_path_and_reaches_the_trace(tmp_path: Path) -> None:
    """An advancement is a transaction like a turn: it saves and reaches the trace panel."""
    game = session(tmp_path)
    for _ in range(3):
        game.state = game.engine.resolve(setback_direction(), game.state, Random(2)).state
    player = player_rules(game.state)
    assert player.growth_marks == 3
    before = player.approaches.bold
    decision = RaiseApproach(approach="bold")

    with pytest.raises(TypeError, match="'story' engine received a Dnd5eAdvancementDecisions"):
        game.advance(Dnd5eAdvancementDecisions(decisions={}))

    facts = game.advance(decision)

    assert [fact.fact for fact in facts] == ["approach-raised", "growth-reset"]
    player = player_rules(game.state)
    assert player.approaches.bold == before + 1
    assert player.growth_marks == 0
    assert FileSaves(tmp_path).load("poc") == game.state
    (entry,) = FileTraces(tmp_path).load("poc")
    assert isinstance(entry, Advance) and entry.facts == facts
    assert game.entries == [entry]


def test_one_open_game_per_slug_and_it_keeps_the_origin_it_was_opened_with(tmp_path: Path) -> None:
    """A page render resolves the session by slug; rebuilding it drops the turn in flight."""
    runtime = Runtime(updated(settings(), saves_dir=tmp_path))
    opened = runtime.session(TARGET)

    assert runtime.session(TARGET) is opened
    assert runtime.session(updated(TARGET, slug="second")).engine is opened.engine
    with pytest.raises(ValueError, match="open session 'poc' plays"):
        runtime.session(updated(TARGET, character_id="someone-else"))
