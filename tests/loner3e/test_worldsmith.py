from support.loner import HUB_PLACE, HUB_SITUATION, KEEPER, hub_world
from support.table import the_campaign

from aidm.core.entities import EntityId
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.loner3e.world import Loner3eSheet
from aidm.engines.scenes.drafts import HubDraft, ReturnDraft, SceneDraft
from aidm.engines.scenes.worldsmith import scene_refusal

ENGINE = Loner3eEngine()


def _draft(**fields: object) -> SceneDraft[Loner3eSheet]:
    base = {
        "place": "deeper-in",
        "title": "Deeper In",
        "question": "Can Kael get further into the cairn before dawn?",
        "situation": HUB_SITUATION,
        "arc": "Farther in, the cairn's own keeper is still owed for the last seal.",
    }
    return SceneDraft[Loner3eSheet].model_validate(base | fields)


RECAP = (
    "Kael broke the cairn's seal, weighed what waited inside, and carried it back up into the "
    "evening air."
)
SUMMARY = (
    "Kael went down into the sealed cairn for Orsa, broke its seal, and found the relic whole; "
    "he carried it back to the guild hall and the job is done, though a passage found beneath "
    "the cairn still waits unspoken."
)


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
            "recap": RECAP,
            "summary": SUMMARY,
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


def test_only_the_players_own_fields_are_checked_for_what_they_have_not_met() -> None:
    """`summary` is the game master's memory; `situation`, `debrief` and `question` are the
    player's, and none of them may hand the player what they have not found."""
    world = hub_world().payload
    stranger = EntityId("stranger")
    world.cast[stranger] = Loner3eSheet(id=stranger, name="Old Man Riley", brief="", known=False)

    named_in_summary = _return_draft().model_copy(
        update={
            "summary": "Old Man Riley wintered alone by the cairn's mouth while Kael broke the "
            "seal below; the relic came up whole and the guild's ledger closes clean, though a "
            "passage found beneath the cairn still waits unspoken."
        }
    )
    assert scene_refusal(named_in_summary, world) is None

    named_in_situation = _return_draft().model_copy(
        update={"situation": f"{HUB_SITUATION} Old Man Riley watches from the doorway."}
    )
    assert scene_refusal(named_in_situation, world) == (
        "the scene needs a situation that does not name what the player has not met: "
        "['Old Man Riley']"
    )

    ided_in_debrief = _return_draft().model_copy(
        update={"debrief": f"The cairn is sealed again; {stranger} saw them off."}
    )
    assert scene_refusal(ided_in_debrief, world) == (
        "the scene needs a debrief that does not name what the player has not met: "
        "['Old Man Riley']"
    )

    hidden = EntityId("buried-chest")
    named_hidden_id_in_question = _return_draft().model_copy(
        update={
            "question": f"What does Kael do about {hidden}, now the job is behind him?",
            "hidden": (hidden,),
            "cast": {hidden: Loner3eSheet(id=hidden, name="A Buried Chest", brief="", known=False)},
        }
    )
    assert scene_refusal(named_hidden_id_in_question, world) == (
        "the scene needs a question that does not name what the player has not met: "
        "['A Buried Chest']"
    )


def test_install_scene_on_a_finished_return_swaps_board_notes_job_keeps_companion() -> None:
    game = hub_world()
    world = game.payload
    scout = EntityId("scout")
    world.cast[scout] = Loner3eSheet(id=scout, name="Scout", brief="A hired scout", known=True)
    world.party = [scout]
    campaign = the_campaign(world.campaign)
    campaign.jobs[-1].finished = True

    facts = ENGINE.install(game, _return_draft())

    world = game.payload
    assert [offer.title for offer in campaign.board] == ["Job 1", "Job 2"]
    assert [fact.kind for fact in facts] == ["job_closed", "scene_opened"]
    assert any(fact.card.startswith("Home: Back at the Guild Hall") for fact in facts)
    assert any("The Sealed Cairn" in note for note in game.notes)
    assert scout in world.present()


def test_install_scene_on_an_open_return_skips_the_growth_note() -> None:
    game = hub_world()
    facts = ENGINE.install(game, _return_draft())
    assert [fact.kind for fact in facts] == ["job_closed", "scene_opened"]
    assert game.notes == []


def _opening(**fields: object) -> SceneDraft[Loner3eSheet]:
    return _draft(
        place=HUB_PLACE,
        present=("keeper",),
        cast={"keeper": Loner3eSheet(id=EntityId("keeper"), name="Keeper", brief="Keeps the hall")},
        **fields,
    )


def test_opening_canon_sets_the_hub_and_board_for_a_campaign_only() -> None:
    offers = [{"title": "A", "pitch": "Take A."}, {"title": "B", "pitch": "Take B."}]
    campaign = the_campaign(
        ENGINE.opening_canon(
            HubDraft[Loner3eSheet].model_validate({**_opening().model_dump(), "offers": offers}), ""
        ).campaign
    )
    assert campaign.place == HUB_PLACE
    assert [offer.title for offer in campaign.board] == ["A", "B"]
    assert ENGINE.opening_canon(_opening(), "").campaign is None
