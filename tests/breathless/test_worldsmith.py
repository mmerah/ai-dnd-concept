from support.breathless import HUB_PLACE, HUB_SITUATION, SITUATION, hub_world, small_world
from support.table import the_campaign

from aidm.core.entities import EntityId
from aidm.core.facts import Fact
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.breathless.engine import BreathlessEngine
from aidm.engines.scenes.drafts import HubDraft, ReturnDraft, SceneDraft
from aidm.engines.scenes.worldsmith import scene_refusal

ENGINE = BreathlessEngine()


def _draft(**fields: object) -> SceneDraft[Person]:
    base = {
        "place": "alley",
        "title": "The Alley",
        "question": "Can they lose the mob in the alley?",
        "situation": SITUATION,
        "arc": "Farther on, the mob's own paymaster still doesn't know Jax's face.",
    }
    return SceneDraft[Person].model_validate({**base, **fields})


def test_the_bar_refuses_a_scene_that_lists_the_player() -> None:
    world = small_world().payload
    assert "put there by code" in (scene_refusal(_draft(present=("Jax", "mira")), world) or "")


def test_the_bar_refuses_a_draft_cast_entry_under_player_id() -> None:
    world = small_world().payload
    draft = _draft(
        cast={PLAYER_ID: Person(id=PLAYER_ID, name="Someone", brief="filed wrongly", known=True)}
    )
    assert "rewrites the player" in (scene_refusal(draft, world) or "")


def test_the_bar_refuses_hiding_someone_met() -> None:
    world = small_world().payload
    assert "already met" in (scene_refusal(_draft(hidden=("mira",)), world) or "")


def test_the_opening_needs_a_cast_member() -> None:
    assert scene_refusal(_draft()) == "the scene needs at least one cast member besides the player"


def test_the_next_scene_needs_one_brought_back() -> None:
    world = small_world().payload
    stranger = EntityId("stranger")
    draft = _draft(
        hidden=(stranger,),
        cast={stranger: Person(id=stranger, name="A Stranger", brief="unknown to the world")},
    )
    assert scene_refusal(draft, world) == (
        "the scene needs at least one existing cast member brought back"
    )


def test_a_dead_draft_cast_member_is_refused() -> None:
    world = small_world().payload
    ghost = EntityId("ghost")
    draft = _draft(
        present=("mira",), cast={ghost: Person(id=ghost, name="Ghost", brief="", alive=False)}
    )
    assert scene_refusal(draft, world) == (
        "the scene needs cast members as the worldsmith may write them: ['ghost: alive']"
    )


def test_a_hidden_multi_word_name_in_situation_is_refused() -> None:
    world = small_world().payload
    stalker = EntityId("stalker")
    situation = f"{SITUATION} Old Man Riley waits by the dumpster."
    draft = _draft(
        situation=situation,
        present=("mira",),
        hidden=(stalker,),
        cast={stalker: Person(id=stalker, name="Old Man Riley", brief="")},
    )
    assert scene_refusal(draft, world) == (
        "the scene needs a situation that does not name what is hidden: ['Old Man Riley']"
    )


def test_install_scene_appends_a_run_and_returns_the_opened_fact() -> None:
    game = small_world()
    facts = ENGINE.install(game, _draft(present=("mira",)))
    assert len(game.payload.runs) == 2
    assert facts == [
        Fact(
            kind="scene_opened",
            trace="the story moves to The Alley",
            told=True,
            card="New scene: The Alley\nAt stake: Can they lose the mob in the alley?",
        ),
    ]


def test_render_worldsmith_lists_the_player_first() -> None:
    prompt = ENGINE.render_next(small_world(), "Explore the alley.", SceneDraft[Person])
    assert prompt.index("Jax[player]") < prompt.index("Mira[mira]")


RECAP = (
    "Jax cleared the pharmacy shelf by shelf, weighed what could be carried, and slipped back "
    "out before the block woke."
)
SUMMARY = (
    "Jax hit the pharmacy for the supplies the camp needed, cleared it room by room, and the "
    "run is done; a locked back room they never opened still waits unspoken."
)


def _return_draft(*, offers: int = 2) -> ReturnDraft[Person]:
    return ReturnDraft[Person].model_validate(
        {
            "place": HUB_PLACE,
            "title": "Back at the Camp",
            "question": "What does Jax do next, now the run is behind them?",
            "situation": HUB_SITUATION,
            "present": ("keeper",),
            "offers": [
                {"title": f"Job {number}", "pitch": f"I take job {number}."}
                for number in range(1, offers + 1)
            ],
            "debrief": "The pharmacy is cleared and the supplies are back.",
            "recap": RECAP,
            "summary": SUMMARY,
        }
    )


def test_a_return_naming_an_unmet_cast_member_in_the_debrief_is_refused() -> None:
    world = hub_world().payload
    stranger = EntityId("stranger")
    world.cast[stranger] = Person(id=stranger, name="Old Man Riley", brief="", known=False)
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
    world.cast[stranger] = Person(id=stranger, name="Old Man Riley", brief="", known=False)

    named_in_summary = _return_draft().model_copy(
        update={
            "summary": "Old Man Riley wintered alone behind the pharmacy while Jax cleared the "
            "shelves; the supplies came back whole and the camp is fed, though a locked back "
            "room still waits unspoken."
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
        update={"debrief": f"The pharmacy is cleared; {stranger} saw them off."}
    )
    assert scene_refusal(ided_in_debrief, world) == (
        "the scene needs a debrief that does not name what the player has not met: "
        "['Old Man Riley']"
    )

    hidden = EntityId("buried-chest")
    named_hidden_id_in_question = _return_draft().model_copy(
        update={
            "question": f"What does Jax do about {hidden}, now the run is behind them?",
            "hidden": (hidden,),
            "cast": {hidden: Person(id=hidden, name="A Buried Chest", brief="", known=False)},
        }
    )
    assert scene_refusal(named_hidden_id_in_question, world) == (
        "the scene needs a question that does not name what the player has not met: "
        "['A Buried Chest']"
    )


def test_install_scene_on_a_return_swaps_the_board_and_notes_nothing() -> None:
    for finished in (True, False):
        game = hub_world()
        campaign = the_campaign(game.payload.campaign)
        campaign.jobs[-1].finished = finished
        facts = ENGINE.install(game, _return_draft())
        assert [offer.title for offer in campaign.board] == ["Job 1", "Job 2"]
        assert [fact.kind for fact in facts] == ["job_closed", "scene_opened"]
        assert game.notes == []


def test_install_scene_on_a_hub_draft_lands_a_home_card() -> None:
    game = hub_world()
    facts = ENGINE.install(game, _return_draft())
    assert any(fact.card.startswith("Home: Back at the Camp") for fact in facts)


def _opening(**fields: object) -> SceneDraft[Person]:
    return _draft(
        place=HUB_PLACE,
        present=("keeper",),
        cast={"keeper": Person(id=EntityId("keeper"), name="Keeper", brief="Holds the camp")},
        **fields,
    )


def test_opening_canon_sets_the_hub_and_board_for_a_campaign_only() -> None:
    offers = [{"title": "A", "pitch": "Take A."}, {"title": "B", "pitch": "Take B."}]
    campaign = the_campaign(
        ENGINE.opening_canon(
            HubDraft[Person].model_validate({**_opening().model_dump(), "offers": offers}), ""
        ).campaign
    )
    assert campaign.place == HUB_PLACE
    assert [offer.title for offer in campaign.board] == ["A", "B"]
    assert ENGINE.opening_canon(_opening(), "").campaign is None
