from pathlib import Path

import pytest
from support.game import ENGINE, loner_sheet
from support.table import LIBRARY, narrowed

from aidm.core.creation import Picks
from aidm.core.entities import Refusal, Slug
from aidm.core.io import ENCODING, Library
from aidm.core.play import DecisionOption
from aidm.engines.base import PLAYER_ID
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.loner3e.pack import Loner3ePack
from aidm.engines.loner3e.world import LUCK_MAX, Loner3eGame
from aidm.engines.packs import SRD_PACK


def test_a_created_character_plays_through_the_authored_load_path(tmp_path: Path) -> None:
    picks: Picks = {
        "concept": "A wandering scribe who counts doors",
        "goal": "Count every door in the old city",
        "motive": "The tally is the only thing that still makes sense",
        "skill-1": "quiet-hands",
        "skill-2": "reads-old-stonework",
        "frailty": "never-walks-away",
        "gear-1": "pry-bar",
        "gear-2": "chalk-and-wire",
    }
    created = ENGINE.create_character(
        "Fen", "A wandering scribe with too many questions.", SRD_PACK, picks
    )
    library = Library(tmp_path, tmp_path)
    library.write_character(created)
    character = library.read_character("fen", ENGINE.id, ENGINE.character)
    scenario = LIBRARY.read_scenario("whispering-vault", {ENGINE.id: ENGINE.scenario})
    state = ENGINE.begin("whispering-vault", scenario, character)
    state = narrowed(state, Loner3eGame)
    made = loner_sheet(state, PLAYER_ID)
    assert made.concept == "A wandering scribe who counts doors"
    assert made.tags == {
        "skill": ["Quiet Hands", "Reads Old Stonework"],
        "frailty": ["Never Walks Away"],
        "gear": ["Pry Bar", "Chalk and Wire"],
    }
    assert made.luck.current == LUCK_MAX


def test_an_illegal_pick_set_is_refused_with_the_reason(tmp_path: Path) -> None:
    legal = _answered(SRD_PACK, {})
    with pytest.raises(Refusal, match="no creation step"):
        ENGINE.create_character("Fen", "", SRD_PACK, {**legal, "class": "fighter"})
    with pytest.raises(Refusal, match="is unanswered"):
        ENGINE.create_character(
            "Fen", "", SRD_PACK, {key: value for key, value in legal.items() if key != "gear-2"}
        )
    with pytest.raises(Refusal, match="offers no"):
        ENGINE.create_character("Fen", "", SRD_PACK, {**legal, "frailty": "unwritten"})
    with pytest.raises(Refusal, match="is unanswered"):
        ENGINE.create_character("Fen", "", SRD_PACK, {**legal, "concept": "  "})
    created = ENGINE.create_character("Fen", "", SRD_PACK, legal)
    library = Library(tmp_path, tmp_path)
    library.write_character(created)
    with pytest.raises(Refusal, match="already exists"):
        library.write_character(created)


def _answered(pack_id: Slug, chosen: Picks) -> Picks:
    """Answers each step with its first option, so later steps appear as earlier ones land."""
    picks = dict(chosen)
    while step := next(
        (
            candidate
            for candidate in ENGINE.creation_steps(pack_id, picks)
            if candidate.id not in picks
        ),
        None,
    ):
        picks[step.id] = step.options[0].id if step.options else "Something written"
    return picks


def test_a_written_pack_never_offers_a_row_the_srd_already_offers(tmp_path: Path) -> None:
    shared = ENGINE.packs.srd().skills[0]
    written = Loner3ePack(
        name="Mine",
        source="",
        license="",
        concepts=(DecisionOption(id="concept", name="Concept"),),
        skills=(shared, DecisionOption(id="own-skill", name="Own Skill")),
        frailties=(DecisionOption(id="frailty", name="Frailty"),),
        gear=(DecisionOption(id="gear", name="Gear"),),
    )
    (tmp_path / "mine.json").write_text(written.model_dump_json(), encoding=ENCODING)
    steps = Loner3eEngine(tmp_path).creation_steps("mine", {})

    offered = [option.id for step in steps if step.id == "skill-1" for option in step.options]

    assert len(offered) == len(set(offered))
    assert "own-skill" in offered
