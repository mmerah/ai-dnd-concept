from pathlib import Path

import pytest
from core_test_support import ENGINES_BUILT, LONER3E, SCENARIOS, updated
from loner3e_test_support import sheet

from aidm.content.io import load_character, load_scenario, write_character
from aidm.engines.core import CharacterCreation, mechanics_of
from aidm.engines.loner3e.rules import LUCK_MAX, Loner3eState
from aidm.engines.registry import begin_game
from aidm.state.creation import Picks
from aidm.state.entities import PLAYER_ID, EngineId

OTHER = EngineId("ruleless")


def test_a_created_character_plays_through_the_authored_load_path(tmp_path: Path) -> None:
    engine = ENGINES_BUILT[LONER3E]
    creation = engine.creation
    picks: Picks = {
        "pack": "srd",
        "concept": "A wandering scribe who counts doors",
        "skill-1": "quiet-hands",
        "skill-2": "reads-old-stonework",
        "frailty": "never-walks-away",
        "gear-1": "pry-bar",
        "gear-2": "chalk-and-wire",
    }
    created, _ = creation.created("Fen", "A wandering scribe with too many questions.", picks)
    write_character(tmp_path, created)
    character = load_character(tmp_path, "fen", engine)
    scenario = load_scenario(SCENARIOS, "whispering-vault", engine)
    state = begin_game(engine, "whispering-vault", scenario, character)
    # The merge joins the new sheet into the scenario's blob rather than replacing it.
    assert mechanics_of(state.world, Loner3eState).twist_pack == "srd"
    made = sheet(state, PLAYER_ID)
    assert made.concept == "A wandering scribe who counts doors"
    assert made.skills == ("Quiet Hands", "Reads Old Stonework")
    assert made.frailties == ("Never Walks Away",)
    assert made.gear == ("Pry Bar", "Chalk and Wire")
    assert made.luck.current == LUCK_MAX


def test_an_illegal_pick_set_is_refused_with_the_reason(tmp_path: Path) -> None:
    creation = ENGINES_BUILT[LONER3E].creation
    legal: Picks = _answered(creation, {"pack": "srd"})
    with pytest.raises(ValueError, match="no creation step"):
        creation.create("Fen", "", {**legal, "class": "fighter"})
    with pytest.raises(ValueError, match="is unanswered"):
        creation.create("Fen", "", {key: value for key, value in legal.items() if key != "gear-2"})
    with pytest.raises(ValueError, match="offers no"):
        creation.create("Fen", "", {**legal, "frailty": "unwritten"})
    with pytest.raises(ValueError, match="is unanswered"):
        creation.create("Fen", "", {**legal, "concept": "  "})
    created, _ = creation.created("Fen", "", legal)
    write_character(tmp_path, created)
    with pytest.raises(ValueError, match="already exists"):
        write_character(tmp_path, created)


def test_one_folder_holds_one_person_across_engines(tmp_path: Path) -> None:
    creation = ENGINES_BUILT[LONER3E].creation
    fen, _ = creation.created("Fen", "A wandering scribe.", _answered(creation, {"pack": "srd"}))
    write_character(tmp_path, fen)

    with pytest.raises(ValueError, match="is 'Fen', not 'Mira'"):
        write_character(tmp_path, updated(fen, engine=OTHER, name="Mira"))

    write_character(tmp_path, updated(fen, engine=OTHER))
    assert load_character(tmp_path, "fen", ENGINES_BUILT[LONER3E]).name == "Fen"


def _answered(creation: CharacterCreation, chosen: Picks) -> Picks:
    """Answers each step with its first option, so later steps appear as earlier ones land."""
    picks = dict(chosen)
    while step := next((one for one in creation.steps(picks) if one.id not in picks), None):
        picks[step.id] = step.options[0].id if step.options else "Something written"
    return picks


def test_the_second_skill_step_drops_what_the_first_one_took() -> None:
    creation = ENGINES_BUILT[LONER3E].creation
    steps = {step.id: step for step in creation.steps({"pack": "srd", "skill-1": "quiet-hands"})}
    assert "quiet-hands" not in {option.id for option in steps["skill-2"].options}
    assert "quiet-hands" in {option.id for option in steps["skill-1"].options}
    legal = _answered(creation, {"pack": "srd"})
    with pytest.raises(ValueError, match="offers no"):
        _ = creation.create("Fen", "", {**legal, "skill-2": legal["skill-1"]})
