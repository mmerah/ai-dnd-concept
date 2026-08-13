from pathlib import Path

import pytest
from core_test_support import SCENARIOS
from loner3e_test_support import LONER3E

from aidm.app.session import begin_game
from aidm.content.store import load_character, load_scenario, write_character
from aidm.engines.counters import read_mechanics
from aidm.engines.loner3e.mechanics import LUCK_MAX, Mechanics
from aidm.engines.loner3e.rules import Loner3eEngine
from aidm.state.base import PLAYER_ID
from aidm.state.creation import Picks


def _creation(engine: Loner3eEngine):
    creation = engine.creation
    assert creation is not None
    return creation


def test_a_created_character_plays_through_the_authored_load_path(tmp_path: Path) -> None:
    engine = Loner3eEngine()
    creation = _creation(engine)
    picks: Picks = {
        "pack": ("srd",),
        "concept": ("wary-relic-hunter",),
        "skills": ("quiet-hands", "reads-old-stonework"),
        "frailty": ("never-walks-away",),
        "gear": ("pry-bar", "chalk-and-wire"),
    }
    created = creation.create("Fen", "A wandering scribe with too many questions.", picks)
    write_character(tmp_path, "fen", LONER3E, created)
    character = load_character(tmp_path, "fen", LONER3E)
    scenario = load_scenario(SCENARIOS, "whispering-vault", LONER3E)
    state = begin_game(engine, scenario, character)
    sheet = read_mechanics(state, Mechanics).sheets[PLAYER_ID]
    assert sheet.skills == ("Quiet Hands", "Reads Old Stonework")
    assert sheet.frailties == ("Never Walks Away",)
    assert sheet.gear == ("Pry Bar", "Chalk and Wire")
    assert sheet.luck.current == LUCK_MAX


def test_an_illegal_pick_set_is_refused_with_the_reason(tmp_path: Path) -> None:
    creation = _creation(Loner3eEngine())
    chosen: Picks = {"pack": ("srd",)}
    legal: Picks = {
        step.id: chosen.get(step.id, tuple(option.id for option in step.options[: step.choose]))
        for step in creation.steps(chosen)
    }
    with pytest.raises(ValueError, match="no creation step"):
        creation.create("Fen", "", {**legal, "class": ("fighter",)})
    with pytest.raises(ValueError, match="exactly 1"):
        creation.create("Fen", "", {**legal, "concept": ()})
    with pytest.raises(ValueError, match="offers no"):
        creation.create("Fen", "", {**legal, "frailty": ("unwritten",)})
    created = creation.create("Fen", "", legal)
    write_character(tmp_path, "fen", LONER3E, created)
    with pytest.raises(ValueError, match="already exists"):
        write_character(tmp_path, "fen", LONER3E, created)
