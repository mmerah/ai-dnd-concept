import pytest
from support.table import (
    ENGINES_BUILT,
    LIBRARY,
    LONER3E,
    SCENARIO_MODELS,
    game,
    narrowed,
    scenario_for,
    updated,
)

from aidm.core.entities import EngineId, Refusal
from aidm.core.model import PackSelection
from aidm.core.play import DecisionOption
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.loner3e.worldsmith import Loner3eBlock, Loner3ePack
from aidm.engines.packs import MAX_SUPPLEMENTS, SRD_PACK, Names, Pack, PackSet

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


def test_new_game_refuses_a_character_made_from_an_unselected_pack() -> None:
    engine = ENGINES_BUILT[LONER3E]
    scenario_id = scenario_for(LONER3E)
    scenario = LIBRARY.read_scenario(scenario_id, SCENARIO_MODELS)
    character = LIBRARY.read_character("kael", engine.id, engine.character)
    stranded = character.model_copy(update={"packs": PackSelection(ids=(SRD_PACK, "other"))})

    with pytest.raises(Refusal, match="'kael' was made with srd, other"):
        engine.new_game(scenario, stranded)


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
    packs = PackSet(engine.id, {**engine.packs.installed, "twin": engine.packs.srd()})

    with pytest.raises(Refusal, match="both define"):
        packs.select(PackSelection(ids=(SRD_PACK, "twin")))


def test_select_refuses_more_than_max_supplements_beside_the_srd() -> None:
    srd = Pack(name="SRD", source="", license="")
    extra = Pack(name="Extra", source="", license="")
    packs = PackSet(TEST_ENGINE, {SRD_PACK: srd, "one": extra, "two": extra, "three": extra})

    with pytest.raises(Refusal, match=f"at most {MAX_SUPPLEMENTS} packs"):
        packs.select(PackSelection(ids=(SRD_PACK, "one", "two", "three")))


def test_sections_shows_adventure_seeds_only_at_the_opening() -> None:
    pack = Pack(name="Test", source="", license="", seeds=("A vanished caravan.",))

    assert "ADVENTURE SEEDS" in dict(pack.sections(opening=True))
    assert "ADVENTURE SEEDS" not in dict(pack.sections(opening=False))


def test_sections_drops_empty_name_lists() -> None:
    empty = Pack(name="Test", source="", license="")
    female_only = Pack(name="Test", source="", license="", names=Names(female=("Elira",)))

    assert "NAMES" not in dict(empty.sections(opening=False))
    assert dict(female_only.sections(opening=False))["NAMES"] == "female: Elira"


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
    packs = PackSet(TEST_ENGINE, {SRD_PACK: pack})

    assert packs.guidance(PackSelection(ids=(SRD_PACK,)), opening=False).startswith("PACK: Test")


def test_rules_sections_is_empty_unless_the_pack_writes_rules() -> None:
    plain = Pack(name="Test", source="", license="")
    with_rules = Pack(name="Test", source="", license="", rules="Spend Luck to reroll once.")
    plain_packs = PackSet(TEST_ENGINE, {SRD_PACK: plain})
    written_packs = PackSet(TEST_ENGINE, {SRD_PACK: with_rules})

    assert plain_packs.rules_sections(PackSelection(ids=(SRD_PACK,))) == ()
    assert written_packs.rules_sections(PackSelection(ids=(SRD_PACK,))) == (
        ("SPECIAL RULES: Test", "Spend Luck to reroll once."),
    )
