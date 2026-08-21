from pathlib import Path

import pytest
from core_test_support import SCENARIOS
from loner3e_test_support import LONER3E

from aidm.app.registry import begin_game, build_engine
from aidm.content.store import load_character, load_scenario, write_character
from aidm.engines.engine import Engine
from aidm.engines.loner3e.mechanics import LUCK_MAX, Mechanics
from aidm.state.base import PLAYER_ID
from aidm.state.creation import CreationStep, Picks


def _creation(engine: Engine):
    creation = engine.creation
    assert creation is not None
    return creation


def test_a_created_character_plays_through_the_authored_load_path(tmp_path: Path) -> None:
    engine = build_engine(LONER3E)
    creation = _creation(engine)
    picks: Picks = {
        "pack": ("srd",),
        "concept": ("A wandering scribe who counts doors",),
        "skills": ("quiet-hands", "reads-old-stonework"),
        "frailty": ("never-walks-away",),
        "gear": ("pry-bar", "chalk-and-wire"),
    }
    created = creation.create("Fen", "A wandering scribe with too many questions.", picks)
    write_character(tmp_path, "fen", LONER3E, created)
    character = load_character(tmp_path, "fen", engine.id, engine.check_overlay)
    scenario = load_scenario(SCENARIOS, "whispering-vault")
    state = begin_game(engine, "whispering-vault", scenario, character)
    sheet = Mechanics.of(state).sheets[PLAYER_ID]
    assert sheet.pack == "srd"
    assert sheet.concept == "A wandering scribe who counts doors"
    assert sheet.skills == ("Quiet Hands", "Reads Old Stonework")
    assert sheet.frailties == ("Never Walks Away",)
    assert sheet.gear == ("Pry Bar", "Chalk and Wire")
    assert sheet.luck.current == LUCK_MAX


def test_an_illegal_pick_set_is_refused_with_the_reason(tmp_path: Path) -> None:
    creation = _creation(build_engine(LONER3E))
    chosen: Picks = {"pack": ("srd",)}
    legal: Picks = {
        step.id: chosen.get(
            step.id,
            tuple(option.id for option in step.options[: step.choose])
            if isinstance(step, CreationStep)
            else ("Something written",) * step.count,
        )
        for step in creation.steps(chosen)
    }
    with pytest.raises(ValueError, match="no creation step"):
        creation.create("Fen", "", {**legal, "class": ("fighter",)})
    with pytest.raises(ValueError, match="exactly 1"):
        creation.create("Fen", "", {**legal, "concept": ()})
    with pytest.raises(ValueError, match="offers no"):
        creation.create("Fen", "", {**legal, "frailty": ("unwritten",)})
    with pytest.raises(ValueError, match="an answer in words"):
        creation.create("Fen", "", {**legal, "concept": ("",)})
    with pytest.raises(ValueError, match="at most 100 characters"):
        creation.create("Fen", "", {**legal, "concept": ("x" * 200,)})
    created = creation.create("Fen", "", legal)
    write_character(tmp_path, "fen", LONER3E, created)
    with pytest.raises(ValueError, match="already exists"):
        write_character(tmp_path, "fen", LONER3E, created)
