from pathlib import Path

import pytest
from core_test_support import SCENARIOS
from oracle_test_support import ORACLE

from aidm.app.session import begin_game
from aidm.content.store import load_character, load_scenario, write_character
from aidm.engines.oracle.mechanics import LUCK_MAX, read
from aidm.engines.oracle.rules import OracleEngine
from aidm.state.base import PLAYER_ID
from aidm.state.creation import CreationStep, Picks


def _creation(engine: OracleEngine):
    creation = engine.creation
    assert creation is not None
    return creation


def test_a_created_character_plays_through_the_authored_load_path(tmp_path: Path) -> None:
    engine = OracleEngine()
    creation = _creation(engine)
    picks: Picks = {
        "concept": ("wary-relic-hunter",),
        "edges": ("quiet-hands", "reads-old-stonework"),
        "burden": ("never-walks-away",),
        "gear": ("pry-bar", "chalk-and-wire"),
    }
    created = creation.create("Fen", "A wandering scribe with too many questions.", picks)
    write_character(tmp_path, "fen", ORACLE, created)
    character = load_character(tmp_path, "fen", ORACLE)
    scenario = load_scenario(SCENARIOS, "whispering-vault", ORACLE)
    state = begin_game(engine, scenario, character)
    sheet = read(state).sheets[PLAYER_ID]
    assert sheet.edges == ("Quiet Hands", "Reads Old Stonework")
    assert sheet.burdens == ("Never Walks Away",)
    assert sheet.gear == ("Pry Bar", "Chalk and Wire")
    assert sheet.luck.current == LUCK_MAX


def test_an_illegal_pick_set_is_refused_with_the_reason(tmp_path: Path) -> None:
    creation = _creation(OracleEngine())
    steps = creation.steps({})
    legal: Picks = {
        step.id: tuple(option.id for option in step.options[: step.choose])
        for step in steps
        if isinstance(step, CreationStep)
    }
    with pytest.raises(ValueError, match="no creation step"):
        creation.create("Fen", "", {**legal, "class": ("fighter",)})
    with pytest.raises(ValueError, match="exactly 1"):
        creation.create("Fen", "", {**legal, "concept": ()})
    with pytest.raises(ValueError, match="offers no"):
        creation.create("Fen", "", {**legal, "burden": ("unwritten",)})
    created = creation.create("Fen", "", legal)
    write_character(tmp_path, "fen", ORACLE, created)
    with pytest.raises(ValueError, match="already exists"):
        write_character(tmp_path, "fen", ORACLE, created)
