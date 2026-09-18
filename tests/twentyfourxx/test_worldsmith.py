import pytest
from support.table import LIBRARY, TWENTYFOURXX
from support.twentyfourxx import ENGINE, SCENE_BASE

from aidm.core.entities import Refusal
from aidm.core.model import AnyScenario, ScenarioMeta
from aidm.engines.scenes.world import SceneProposal
from aidm.engines.twentyfourxx.pack import SheetProposal
from aidm.engines.twentyfourxx.world import Crewmate, TwentyfourxxCharacter

SRD = ENGINE.packs.srd()


def test_sheet_check_accepts_a_muscle_with_intimidation_and_shooting() -> None:
    draft = SheetProposal(
        specialty="Muscle", skills={"Intimidation": 8, "Shooting": 8}, items=("Firearm",)
    )
    draft.check((SRD,))


def test_sheet_check_refuses_an_unknown_specialty() -> None:
    draft = SheetProposal(specialty="Wizard", skills={"Shooting": 8}, items=())
    with pytest.raises(Refusal, match="Wizard"):
        draft.check((SRD,))


def _draft(**fields: object) -> SceneProposal[Crewmate]:
    return SceneProposal[Crewmate].model_validate(dict(SCENE_BASE) | fields)


def _built(draft: SceneProposal[Crewmate]) -> AnyScenario:
    return ENGINE.build_scenario(
        ScenarioMeta(title="Loading Bay", premise="", scope="One tense night shift."),
        "srd",
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
