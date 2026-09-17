from pathlib import Path

import pytest
from support import sixth
from support.table import (
    ENGINES_BUILT,
    LIBRARY,
    LONER3E,
    SCENARIO_MODELS,
    TWENTYFOURXX,
    game,
    narrowed,
    scenario_for,
    updated,
)

from aidm.core.entities import EngineId, Refusal
from aidm.core.io import ENCODING
from aidm.core.model import Character, PackSelection
from aidm.core.play import DecisionOption
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.loner3e.worldsmith import Loner3eBlock, Loner3ePack
from aidm.engines.packs import MAX_SUPPLEMENTS, SRD_PACK, Names, Pack, PackSet, read_packs
from aidm.engines.twentyfourxx.engine import TwentyfourxxEngine
from aidm.engines.twentyfourxx.worldsmith import TwentyfourxxPack

TEST_ENGINE = EngineId("test")


def _loner3e_pack(name: str) -> Loner3ePack:
    return Loner3ePack(
        name=name,
        source="",
        license="",
        concepts=(DecisionOption(id="concept", label="Concept"),),
        skills=(DecisionOption(id="skill", label="Skill"),),
        frailties=(DecisionOption(id="frailty", label="Frailty"),),
        gear=(DecisionOption(id="gear", label="Gear"),),
    )


def test_read_packs_lists_a_written_pack_alongside_the_shipped_ones(tmp_path: Path) -> None:
    shipped = ENGINES_BUILT[LONER3E].directory / "packs"
    (tmp_path / "mine.json").write_text(_loner3e_pack("Mine").model_dump_json(), encoding=ENCODING)

    packs = read_packs(LONER3E, shipped, tmp_path, Loner3ePack)

    assert "mine" in packs.written
    assert "mine" in packs.installed
    assert "mine" not in packs.shipped


def test_read_packs_skips_a_written_pack_that_shadows_a_shipped_id(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    shipped = ENGINES_BUILT[LONER3E].directory / "packs"
    (tmp_path / "srd.json").write_text(
        _loner3e_pack("Fake SRD").model_dump_json(), encoding=ENCODING
    )

    packs = read_packs(LONER3E, shipped, tmp_path, Loner3ePack)

    assert "is a shipped pack" in caplog.text
    assert packs.written == {}
    assert packs.installed[SRD_PACK] == packs.shipped[SRD_PACK]


def test_read_packs_skips_a_written_file_that_is_not_a_pack(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    shipped = ENGINES_BUILT[LONER3E].directory / "packs"
    (tmp_path / "broken.json").write_text('{"name": 1}', encoding=ENCODING)
    (tmp_path / "mine.json").write_text(_loner3e_pack("Mine").model_dump_json(), encoding=ENCODING)

    packs = read_packs(LONER3E, shipped, tmp_path, Loner3ePack)

    assert caplog.text
    assert "broken" not in packs.installed
    assert "mine" in packs.installed


def test_new_game_refuses_a_character_made_from_an_unselected_pack() -> None:
    engine = ENGINES_BUILT[LONER3E]
    scenario_id = scenario_for(LONER3E)
    scenario = LIBRARY.read_scenario(scenario_id, SCENARIO_MODELS)
    character = LIBRARY.read_character("kael", engine.id, engine.character)
    stranded = character.model_copy(update={"packs": PackSelection(ids=(SRD_PACK, "other"))})

    with pytest.raises(Refusal, match="'kael' was made with srd, other"):
        engine.begin(scenario_id, scenario, stranded)


def test_new_game_accepts_a_character_made_from_a_subset_of_the_scenarios_packs() -> None:
    engine = ENGINES_BUILT[LONER3E]
    scenario_id = scenario_for(LONER3E)
    scenario = LIBRARY.read_scenario(scenario_id, SCENARIO_MODELS)
    wider = scenario.model_copy(update={"packs": PackSelection(ids=(SRD_PACK, "ap01-fantasy"))})
    character = LIBRARY.read_character("kael", engine.id, engine.character)

    assert engine.begin(scenario_id, wider, character).packs == wider.packs


def test_select_refuses_a_selection_without_the_srd() -> None:
    engine, state = game(LONER3E)
    state = updated(state, packs=PackSelection(ids=("ap01-fantasy",)))

    with pytest.raises(Refusal, match="plays the 'srd' tables"):
        engine.validate(state)


def test_select_refuses_two_packs_that_define_the_same_id() -> None:
    engine = narrowed(ENGINES_BUILT[LONER3E], Loner3eEngine)
    packs = PackSet(engine.id, {**engine.packs.installed, "twin": engine.packs.srd()}, {})

    with pytest.raises(Refusal, match="both define"):
        packs.select(PackSelection(ids=(SRD_PACK, "twin")))


def test_select_refuses_more_than_max_supplements_beside_the_srd() -> None:
    srd = Pack(name="SRD", source="", license="")
    extra = Pack(name="Extra", source="", license="")
    packs = PackSet(TEST_ENGINE, {SRD_PACK: srd, "one": extra, "two": extra, "three": extra}, {})

    with pytest.raises(Refusal, match=f"at most {MAX_SUPPLEMENTS} packs"):
        packs.select(PackSelection(ids=(SRD_PACK, "one", "two", "three")))


def test_sections_shows_adventure_seeds_only_at_the_opening() -> None:
    pack = Pack(name="Test", source="", license="", seeds=("A vanished caravan.",))

    assert "ADVENTURE SEEDS" in dict(pack.sections(opening=True))
    assert "ADVENTURE SEEDS" not in dict(pack.sections(opening=False))


def test_sections_drops_empty_name_lists() -> None:
    empty = Pack(name="Test", source="", license="")
    female_only = Pack(name="Test", source="", license="", names=Names(female=("Elira",)))
    with_neutral = Pack(
        name="Test", source="", license="", names=Names(female=("Elira",), neutral=("Ash",))
    )

    assert "NAMES" not in dict(empty.sections(opening=False))
    assert dict(female_only.sections(opening=False))["NAMES"] == "female: Elira"
    assert dict(with_neutral.sections(opening=False))["NAMES"] == "female: Elira\nneutral: Ash"


def test_loner3e_pack_sections_render_trait_tags_and_factions() -> None:
    pack = _loner3e_pack("Test").model_copy(
        update={
            "factions": (
                Loner3eBlock(
                    name="The Watch",
                    concept="Keeps order",
                    skills=("Discipline",),
                    frailties=("Slow to bend",),
                ),
            )
        }
    )

    sections = dict(pack.sections(opening=False))

    assert sections["TRAIT TAGS"] == (
        "concepts: Concept\nskills: Skill\nfrailties: Frailty\ngear: Gear"
    )
    assert sections["FACTIONS"] == (
        "- The Watch — Keeps order; skills: Discipline; frailties: Slow to bend"
    )


def test_pack_set_guidance_starts_with_pack_for_a_selection() -> None:
    pack = Pack(name="Test", source="", license="", setting="A quiet border town.")
    packs = PackSet(TEST_ENGINE, {SRD_PACK: pack}, {})

    assert packs.guidance(PackSelection(ids=(SRD_PACK,)), opening=False).startswith("PACK: Test")


def test_rules_sections_is_empty_unless_the_pack_writes_rules() -> None:
    plain = Pack(name="Test", source="", license="")
    with_rules = Pack(name="Test", source="", license="", rules="Spend Luck to reroll once.")
    plain_packs = PackSet(TEST_ENGINE, {SRD_PACK: plain}, {})
    written_packs = PackSet(TEST_ENGINE, {SRD_PACK: with_rules}, {})

    assert plain_packs.rules_sections(PackSelection(ids=(SRD_PACK,))) == ()
    assert written_packs.rules_sections(PackSelection(ids=(SRD_PACK,))) == (
        ("SPECIAL RULES: Test", "Spend Luck to reroll once."),
    )


def test_a_twentyfourxx_supplement_carries_no_skills_of_its_own() -> None:
    engine = narrowed(ENGINES_BUILT[TWENTYFOURXX], TwentyfourxxEngine)
    packs = PackSet(
        engine.id,
        {**engine.packs.installed, "extra": TwentyfourxxPack(name="Extra", source="", license="")},
        {},
    )

    assert packs.select(PackSelection(ids=(SRD_PACK, "extra"))).ids == (SRD_PACK, "extra")


def test_the_seam_admits_a_character_no_wider_than_the_scenario(tmp_path: Path) -> None:
    engine = sixth.installed(tmp_path)
    made_with = Character[Person](
        id="wren",
        engine=engine.id,
        packs=PackSelection(ids=("mine",)),
        payload=Person(id=PLAYER_ID, name="Wren", brief="A quiet scout", known=True),
    )
    packless = made_with.model_copy(update={"packs": None})

    engine.admit(PackSelection(ids=("mine",)), packless)

    with pytest.raises(Refusal, match="this scenario plays no pack"):
        engine.admit(None, made_with)


def test_seeds_lists_the_selected_packs_seeds_in_order() -> None:
    first = Pack(name="First", source="", license="", seeds=("A vanished caravan.",))
    second = Pack(name="Second", source="", license="", seeds=("A debt come due.",))
    packs = PackSet(TEST_ENGINE, {SRD_PACK: first, "second": second}, {})

    assert packs.seeds(None) == ()
    assert packs.seeds(PackSelection(ids=("second", SRD_PACK))) == (
        "A debt come due.",
        "A vanished caravan.",
    )
