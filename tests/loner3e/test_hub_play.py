from loner3e_test_support import HUB_PLACE, HUB_SITUATION, KEEPER, hub_world

from aidm.core.entities import EntityId
from aidm.engines.loner3e.engine import GROWTH_NOTE
from aidm.engines.loner3e.world import Loner3eSheet
from aidm.engines.scenes.drafts import HubDraft, ReturnDraft, SceneDraft
from aidm.engines.scenes.world import scene_refusal
from aidm.engines.scenes.worldsmith import install_scene, opening_canon


def _draft(**fields: object) -> SceneDraft[Loner3eSheet]:
    base = {
        "place": "deeper-in",
        "title": "Deeper In",
        "question": "Can Kael get further into the cairn before dawn?",
        "situation": HUB_SITUATION,
    }
    return SceneDraft[Loner3eSheet].model_validate({**base, **fields})


def _return_draft(*, offers: int = 2) -> ReturnDraft[Loner3eSheet]:
    return ReturnDraft[Loner3eSheet].model_validate(
        {
            "place": HUB_PLACE,
            "title": "Back at the Guild Hall",
            "question": "What does Kael do next, now the job is behind him?",
            "situation": HUB_SITUATION,
            "present": (KEEPER,),
            "offers": [
                {"title": f"Job {number}", "pitch": f"I take job {number}."}
                for number in range(1, offers + 1)
            ],
            "debrief": "The cairn is sealed again and the relic is recovered.",
        }
    )


def test_a_return_naming_an_unmet_cast_member_in_the_debrief_is_refused() -> None:
    world = hub_world().payload
    stranger = EntityId("stranger")
    world.cast[stranger] = Loner3eSheet(id=stranger, name="Old Man Riley", brief="", known=False)
    draft = _return_draft().model_copy(update={"debrief": "Old Man Riley saw them off with a nod."})
    assert scene_refusal(draft, world) == (
        "the scene needs a debrief that does not name what the player has not met: "
        "['Old Man Riley']"
    )


def test_install_scene_on_a_finished_return_swaps_board_notes_job_keeps_companion() -> None:
    game = hub_world()
    world = game.payload
    scout = EntityId("scout")
    world.cast[scout] = Loner3eSheet(id=scout, name="Scout", brief="A hired scout", known=True)
    world.party = [scout]
    world.jobs[-1].finished = True

    facts = install_scene(game, _return_draft(), finished_note=GROWTH_NOTE)

    world = game.payload
    assert [offer.title for offer in world.board] == ["Job 1", "Job 2"]
    assert [fact.kind for fact in facts] == ["job_closed", "scene_opened"]
    assert any(fact.card.startswith("Home: Back at the Guild Hall") for fact in facts)
    assert any("The Sealed Cairn" in note for note in game.notes)
    assert scout in world.present()


def test_install_scene_on_an_open_return_skips_the_growth_note() -> None:
    game = hub_world()
    facts = install_scene(game, _return_draft(), finished_note=GROWTH_NOTE)
    assert [fact.kind for fact in facts] == ["job_closed", "scene_opened"]
    assert game.notes == ()


def _opening(**fields: object) -> SceneDraft[Loner3eSheet]:
    return _draft(
        place=HUB_PLACE,
        present=("keeper",),
        cast={"keeper": Loner3eSheet(id=EntityId("keeper"), name="Keeper", brief="Keeps the hall")},
        **fields,
    )


def test_opening_canon_sets_the_hub_and_board_for_a_campaign_only() -> None:
    offers = [{"title": "A", "pitch": "Take A."}, {"title": "B", "pitch": "Take B."}]
    campaign = opening_canon(
        HubDraft[Loner3eSheet].model_validate({**_opening().model_dump(), "offers": offers}),
        "",
        Loner3eSheet,
    )
    assert campaign.hub == HUB_PLACE
    assert [offer.title for offer in campaign.board] == ["A", "B"]
    assert opening_canon(_opening(), "", Loner3eSheet).hub is None
