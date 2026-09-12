import re

import pytest
from support.table import LIBRARY, TWENTYFOURXX
from support.twentyfourxx import ENGINE, KESTREL, SABLE, SITUATION, small_world

from aidm.core.entities import Refusal
from aidm.core.model import AnyScenario, PackSelection, ScenarioMeta
from aidm.engines.scenes.tools import SceneDraft
from aidm.engines.scenes.worldsmith import check_scene
from aidm.engines.twentyfourxx.world import Crewmate, CrewSheet, TwentyfourxxCharacter
from aidm.engines.twentyfourxx.worldsmith import SheetDraft

SRD = ENGINE.packs["srd"]


def test_sheet_check_accepts_a_muscle_with_intimidation_and_shooting() -> None:
    draft = SheetDraft(
        specialty="Muscle", skills={"Intimidation": 8, "Shooting": 8}, items=("Firearm",)
    )
    draft.check(SRD)


def test_sheet_check_refuses_an_unknown_specialty() -> None:
    draft = SheetDraft(specialty="Wizard", skills={"Shooting": 8}, items=())
    with pytest.raises(Refusal, match="Wizard"):
        draft.check(SRD)


def test_sheet_check_refuses_a_skill_neither_listed_nor_granted() -> None:
    draft = SheetDraft(specialty="Muscle", skills={"Sorcery": 8}, items=())
    with pytest.raises(Refusal, match="Sorcery"):
        draft.check(SRD)


def test_sheet_check_accepts_medicine_granted_by_medic() -> None:
    draft = SheetDraft(specialty="Face", skills={"Medicine": 8}, items=())
    draft.check(SRD)


def test_the_pack_s_android_case_carries_the_kit() -> None:
    android = next(origin for origin in SRD.origins if origin.label == "Android")
    case = next(body for body in android.choice if body.label == "Case")
    assert case.kit is not None
    assert case.kit.name == "Case"


def _draft(**fields: object) -> SceneDraft[Crewmate]:
    base = {
        "place": "bay-office",
        "title": "The Bay Office",
        "focus": "Can they slip past the night crew before the lights return?",
        "situation": SITUATION,
        "arc": "Farther in, the fixer's own supplier still owes for the last load.",
    }
    return SceneDraft[Crewmate].model_validate(base | fields)


def _built(draft: SceneDraft[Crewmate]) -> AnyScenario:
    return ENGINE.build_scenario(
        ScenarioMeta(title="Loading Bay", premise="", scope="One tense night shift."),
        PackSelection(primary="srd"),
        draft,
        "",
        draft.situation,
    )


def test_apply_scene_resolves_present_by_name() -> None:
    world = small_world().payload
    world.apply_scene(_draft(present=("Kestrel", "sable")))
    assert SABLE in world.present()


def test_apply_scene_resolves_present_by_id_too() -> None:
    world = small_world().payload
    world.apply_scene(_draft(present=(str(SABLE),)))
    assert SABLE in world.present()


def test_apply_scene_marks_present_cast_known() -> None:
    world = small_world().payload
    world.apply_scene(_draft(present=("sable",)))
    assert world.cast[SABLE].known is True


def test_apply_scene_lands_new_cast() -> None:
    world = small_world().payload
    stranger = "stranger"
    world.apply_scene(
        _draft(
            present=("kestrel", "stranger"),
            cast={stranger: Crewmate(id=stranger, name="A Stranger", brief="unknown to the world")},
        ),
    )
    assert stranger in world.cast


def test_apply_scene_re_files_an_existing_cast_member_as_a_new_brief_alone() -> None:
    world = small_world().payload
    draft = _draft(
        present=("kestrel",),
        cast={KESTREL: Crewmate(id=KESTREL, name="Another Kestrel", brief="rewritten")},
    )

    world.apply_scene(draft)

    assert (world.cast[KESTREL].name, world.cast[KESTREL].brief) == ("Kestrel", "rewritten")


def test_the_bar_refuses_a_misfiled_cast_entry() -> None:
    world = small_world().payload
    stranger = "stranger"
    other = "other"
    draft = _draft(
        present=("stranger",),
        cast={stranger: Crewmate(id=other, name="A Stranger", brief="filed wrongly")},
    )
    with pytest.raises(Refusal, match="is filed under"):
        check_scene(draft, world)


def test_the_bar_refuses_present_hidden_overlap() -> None:
    world = small_world().payload
    with pytest.raises(
        Refusal, match=re.escape("nobody listed as both present and hidden: ['sable']")
    ):
        check_scene(_draft(present=("sable",), hidden=("sable",)), world)


def test_the_opening_refuses_a_present_name_that_exists_nowhere() -> None:
    draft = _draft(present=("nobody",))
    with pytest.raises(Refusal, match="these name nobody"):
        check_scene(draft)


def test_a_sheeted_draft_cast_member_is_refused() -> None:
    world = small_world().payload
    stranger = "stranger"
    draft = _draft(
        present=("kestrel", "stranger"),
        cast={
            stranger: Crewmate(
                id=stranger, name="Stranger", brief="", sheet=CrewSheet(specialty="Muscle")
            )
        },
    )
    with pytest.raises(Refusal, match="a sheet"):
        check_scene(draft, world)


def test_the_bar_refuses_a_scene_that_lists_the_player_or_the_party() -> None:
    world = small_world().payload
    world.party = [KESTREL]
    with pytest.raises(Refusal, match=re.escape("they are put there by code: ['kestrel']")):
        check_scene(_draft(present=("kestrel", "sable")), world)
    with pytest.raises(
        Refusal, match=re.escape("they are put there by code: ['kestrel', 'player']")
    ):
        check_scene(_draft(present=("player", "kestrel")), world)


def test_apply_scene_puts_the_party_first_in_the_new_run() -> None:
    world = small_world().payload
    world.party = [KESTREL]
    world.apply_scene(_draft(present=("sable",)))
    assert world.present() == [KESTREL, SABLE]


def test_install_scene_names_who_travelled_in_the_trace() -> None:
    game = small_world()
    game.payload.party = [KESTREL]
    facts = ENGINE.install(game, _draft(present=("sable",)))
    assert facts[0].trace == ("the scene opens: The Bay Office, the player travelling with Kestrel")


def test_render_worldsmith_says_who_travels_with_the_player() -> None:
    game = small_world()
    game.payload.party = [KESTREL]
    prompt = ENGINE.render_next(game, "Explore the bay.")
    assert "travels with the player" in prompt


def test_new_game_marks_present_known() -> None:
    stranger = "stranger"
    draft = _draft(
        present=(stranger,),
        cast={stranger: Crewmate(id=stranger, name="A Stranger", brief="new to the world")},
    )
    character = LIBRARY.read_character("kael", TWENTYFOURXX, TwentyfourxxCharacter)
    world = ENGINE.new_game(_built(draft), character)
    assert world.cast[stranger].known is True


def test_build_scenario_stamps_the_engine_id() -> None:
    stranger = "stranger"
    draft = _draft(
        present=(stranger,),
        cast={stranger: Crewmate(id=stranger, name="A Stranger", brief="new to the world")},
    )
    assert _built(draft).engine == TWENTYFOURXX
