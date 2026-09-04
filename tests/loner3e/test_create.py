from pathlib import Path

import pytest
from support.loner import loner_sheet
from support.table import ENGINES_BUILT, LIBRARY, LONER3E, updated

from aidm.core.creation import Picks
from aidm.core.entities import EngineId, Refusal
from aidm.core.io import Library
from aidm.engines.base import PLAYER_ID
from aidm.engines.loner3e.world import LUCK_MAX, Loner3eGame
from aidm.engines.seam import AnyEngine

OTHER = EngineId("ruleless")


def test_a_created_character_plays_through_the_authored_load_path(tmp_path: Path) -> None:
    engine = ENGINES_BUILT[LONER3E]
    picks: Picks = {
        "pack": "srd",
        "concept": "A wandering scribe who counts doors",
        "goal": "Count every door in the old city",
        "motive": "The tally is the only thing that still makes sense",
        "skill-1": "quiet-hands",
        "skill-2": "reads-old-stonework",
        "frailty": "never-walks-away",
        "gear-1": "pry-bar",
        "gear-2": "chalk-and-wire",
    }
    created = engine.create_character("Fen", "A wandering scribe with too many questions.", picks)
    library = Library(tmp_path, tmp_path)
    library.write_character(created)
    character = library.read_character("fen", engine.id, engine.character)
    scenario = LIBRARY.read_scenario("whispering-vault", {engine.id: engine.scenario})
    state = engine.begin("whispering-vault", scenario, character)
    assert isinstance(state, Loner3eGame), "the Loner engine began another game type"
    made = loner_sheet(state, PLAYER_ID)
    assert made.concept == "A wandering scribe who counts doors"
    assert made.tags == {
        "skill": ["Quiet Hands", "Reads Old Stonework"],
        "frailty": ["Never Walks Away"],
        "gear": ["Pry Bar", "Chalk and Wire"],
    }
    assert made.luck.current == LUCK_MAX


def test_an_illegal_pick_set_is_refused_with_the_reason(tmp_path: Path) -> None:
    engine = ENGINES_BUILT[LONER3E]
    legal: Picks = _answered(engine, {"pack": "srd"})
    with pytest.raises(Refusal, match="no creation step"):
        engine.create_character("Fen", "", {**legal, "class": "fighter"})
    with pytest.raises(Refusal, match="is unanswered"):
        engine.create_character(
            "Fen", "", {key: value for key, value in legal.items() if key != "gear-2"}
        )
    with pytest.raises(Refusal, match="offers no"):
        engine.create_character("Fen", "", {**legal, "frailty": "unwritten"})
    with pytest.raises(Refusal, match="is unanswered"):
        engine.create_character("Fen", "", {**legal, "concept": "  "})
    created = engine.create_character("Fen", "", legal)
    library = Library(tmp_path, tmp_path)
    library.write_character(created)
    with pytest.raises(Refusal, match="already exists"):
        library.write_character(created)


def test_one_folder_holds_one_person_across_engines(tmp_path: Path) -> None:
    engine = ENGINES_BUILT[LONER3E]
    fen = engine.create_character("Fen", "A wandering scribe.", _answered(engine, {"pack": "srd"}))
    library = Library(tmp_path, tmp_path)
    library.write_character(fen)

    mira = updated(fen, engine=OTHER, payload=updated(fen.payload, name="Mira"))
    with pytest.raises(Refusal, match="is 'Fen', not 'Mira'"):
        library.write_character(mira)

    library.write_character(updated(fen, engine=OTHER))
    assert library.read_character("fen", engine.id, engine.character).payload.name == "Fen"


def _answered(engine: AnyEngine, chosen: Picks) -> Picks:
    """Answers each step with its first option, so later steps appear as earlier ones land."""
    picks = dict(chosen)
    while step := next(
        (candidate for candidate in engine.creation_steps(picks) if candidate.id not in picks), None
    ):
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
    with pytest.raises(Refusal, match="offers no"):
        _ = engine.create_character("Fen", "", {**legal, "skill-2": legal["skill-1"]})
