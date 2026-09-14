import pytest
from support.table import LIBRARY, TWENTYFOURXX
from support.twentyfourxx import ENGINE, SCENE_BASE

from aidm.core.entities import Refusal
from aidm.core.model import AnyScenario, PackSelection, ScenarioMeta
from aidm.engines.scenes.tools import SceneDraft
from aidm.engines.twentyfourxx.world import Crewmate, TwentyfourxxCharacter
from aidm.engines.twentyfourxx.worldsmith import SheetDraft

SRD = ENGINE.packs.srd()


def test_sheet_check_accepts_a_muscle_with_intimidation_and_shooting() -> None:
    draft = SheetDraft(
        specialty="Muscle", skills={"Intimidation": 8, "Shooting": 8}, items=("Firearm",)
    )
    draft.check((SRD,))


def test_sheet_check_refuses_an_unknown_specialty() -> None:
    draft = SheetDraft(specialty="Wizard", skills={"Shooting": 8}, items=())
    with pytest.raises(Refusal, match="Wizard"):
        draft.check((SRD,))


def test_sheet_check_accepts_an_invented_skill_but_still_refuses_an_unknown_specialty() -> None:
    draft = SheetDraft(specialty="Muscle", skills={"Sabotage": 8}, items=())
    draft.check((SRD,))

    draft = SheetDraft(specialty="Wizard", skills={"Sabotage": 8}, items=())
    with pytest.raises(Refusal, match="Wizard"):
        draft.check((SRD,))


def test_sheet_skill_die_still_rejects_a_d6_or_a_d20() -> None:
    with pytest.raises(ValueError):
        SheetDraft.model_validate({"specialty": "Muscle", "skills": {"Sabotage": 6}, "items": ()})
    with pytest.raises(ValueError):
        SheetDraft.model_validate({"specialty": "Muscle", "skills": {"Sabotage": 20}, "items": ()})


def test_sheet_check_accepts_medicine_granted_by_medic() -> None:
    draft = SheetDraft(specialty="Face", skills={"Medicine": 8}, items=())
    draft.check((SRD,))


def test_the_pack_s_android_case_carries_the_kit() -> None:
    android = next(origin for origin in SRD.origins if origin.label == "Android")
    case = next(body for body in android.choice if body.label == "Case")
    assert case.kit is not None
    assert case.kit.name == "Case"


def _draft(**fields: object) -> SceneDraft[Crewmate]:
    return SceneDraft[Crewmate].model_validate(dict(SCENE_BASE) | fields)


def _built(draft: SceneDraft[Crewmate]) -> AnyScenario:
    return ENGINE.build_scenario(
        ScenarioMeta(title="Loading Bay", premise="", scope="One tense night shift."),
        PackSelection(ids=("srd",)),
        draft,
        "",
        draft.situation,
    )


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
