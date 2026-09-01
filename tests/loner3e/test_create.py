from pathlib import Path

import pytest
from core_test_support import ENGINES_BUILT, LONER3E, SCENARIOS, loner_sheet, updated

from aidm.core.creation import Picks
from aidm.core.entities import PLAYER_ID, EngineId
from aidm.core.io import load_character, read_scenario, write_character
from aidm.engines.core import AnyEngine
from aidm.engines.loner3e.state import LUCK_MAX, Loner3eGame
from aidm.engines.registry import begin_game

OTHER = EngineId("ruleless")


def test_a_created_character_plays_through_the_authored_load_path(tmp_path: Path) -> None:
    engine = ENGINES_BUILT[LONER3E]
    picks: Picks = {
        "pack": "srd",
        "concept": "A wandering scribe who counts doors",
        "skill-1": "quiet-hands",
        "skill-2": "reads-old-stonework",
        "frailty": "never-walks-away",
        "gear-1": "pry-bar",
        "gear-2": "chalk-and-wire",
    }
    created = engine.create_character("Fen", "A wandering scribe with too many questions.", picks)
    write_character(tmp_path, created)
    character = load_character(tmp_path, "fen", engine.id, engine.character)
    scenario = read_scenario(SCENARIOS, "whispering-vault", {engine.id: engine.scenario})
    state = begin_game(engine, "whispering-vault", scenario, character)
    if not isinstance(state, Loner3eGame):
        raise AssertionError("the Loner engine began another game type")
    assert state.payload.twist_pack == "srd"
    made = loner_sheet(state, PLAYER_ID)
    assert made.concept == "A wandering scribe who counts doors"
    assert made.skills == ("Quiet Hands", "Reads Old Stonework")
    assert made.frailties == ("Never Walks Away",)
    assert made.gear == ("Pry Bar", "Chalk and Wire")
    assert made.luck.current == LUCK_MAX


def test_an_illegal_pick_set_is_refused_with_the_reason(tmp_path: Path) -> None:
    engine = ENGINES_BUILT[LONER3E]
    legal: Picks = _answered(engine, {"pack": "srd"})
    with pytest.raises(ValueError, match="no creation step"):
        engine.create_character("Fen", "", {**legal, "class": "fighter"})
    with pytest.raises(ValueError, match="is unanswered"):
        engine.create_character(
            "Fen", "", {key: value for key, value in legal.items() if key != "gear-2"}
        )
    with pytest.raises(ValueError, match="offers no"):
        engine.create_character("Fen", "", {**legal, "frailty": "unwritten"})
    with pytest.raises(ValueError, match="is unanswered"):
        engine.create_character("Fen", "", {**legal, "concept": "  "})
    created = engine.create_character("Fen", "", legal)
    write_character(tmp_path, created)
    with pytest.raises(ValueError, match="already exists"):
        write_character(tmp_path, created)


def test_one_folder_holds_one_person_across_engines(tmp_path: Path) -> None:
    engine = ENGINES_BUILT[LONER3E]
    fen = engine.create_character("Fen", "A wandering scribe.", _answered(engine, {"pack": "srd"}))
    write_character(tmp_path, fen)

    with pytest.raises(ValueError, match="is 'Fen', not 'Mira'"):
        write_character(tmp_path, updated(fen, engine=OTHER, name="Mira"))

    write_character(tmp_path, updated(fen, engine=OTHER))
    engine = ENGINES_BUILT[LONER3E]
    assert load_character(tmp_path, "fen", engine.id, engine.character).name == "Fen"


def _answered(engine: AnyEngine, chosen: Picks) -> Picks:
    """Answers each step with its first option, so later steps appear as earlier ones land."""
    picks = dict(chosen)
    while step := next((one for one in engine.creation_steps(picks) if one.id not in picks), None):
        picks[step.id] = step.options[0].id if step.options else "Something written"
    return picks


def test_the_second_skill_step_drops_what_the_first_one_took() -> None:
    engine = ENGINES_BUILT[LONER3E]
    steps = {
        step.id: step for step in engine.creation_steps({"pack": "srd", "skill-1": "quiet-hands"})
    }
    assert "quiet-hands" not in {option.id for option in steps["skill-2"].options}
    assert "quiet-hands" in {option.id for option in steps["skill-1"].options}
    legal = _answered(engine, {"pack": "srd"})
    with pytest.raises(ValueError, match="offers no"):
        _ = engine.create_character("Fen", "", {**legal, "skill-2": legal["skill-1"]})
