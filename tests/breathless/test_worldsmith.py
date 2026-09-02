import pytest
from breathless_test_support import (
    HUB_PLACE,
    HUB_SITUATION,
    MIRA,
    SITUATION,
    hub_world,
    small_world,
)

from aidm.core.entities import EntityId
from aidm.core.facts import Fact
from aidm.engines.breathless.world import Npc
from aidm.engines.breathless.worldsmith import (
    HubDraft,
    ReturnDraft,
    SceneDraft,
    apply_scene,
    install_scene,
    opening_canon,
    render_worldsmith,
    scene_refusal,
)
from aidm.engines.core import PLAYER_ID


def _draft(**fields: object) -> SceneDraft:
    base = {
        "place": "alley",
        "title": "The Alley",
        "question": "Can they lose the mob in the alley?",
        "situation": SITUATION,
    }
    return SceneDraft.model_validate({**base, **fields})


def test_apply_scene_drops_the_player_from_present() -> None:
    world = small_world().payload.world
    apply_scene(world, _draft(present=("Jax", "mira")))
    assert PLAYER_ID not in world.run.present
    assert MIRA in world.run.present


def test_apply_scene_refuses_a_draft_cast_entry_under_player_id() -> None:
    world = small_world().payload.world
    draft = _draft(
        cast={PLAYER_ID: Npc(id=PLAYER_ID, name="Someone", brief="filed wrongly", known=True)}
    )
    with pytest.raises(ValueError, match="rewrites the player"):
        apply_scene(world, draft)


def test_apply_scene_refuses_hiding_someone_met() -> None:
    world = small_world().payload.world
    with pytest.raises(ValueError, match="already met"):
        apply_scene(world, _draft(hidden=("mira",)))


def test_the_opening_needs_a_cast_member() -> None:
    assert scene_refusal(_draft()) == "the scene needs at least one cast member besides the player"


def test_the_next_scene_needs_one_brought_back() -> None:
    world = small_world().payload.world
    stranger = EntityId("stranger")
    draft = _draft(
        hidden=(stranger,),
        cast={stranger: Npc(id=stranger, name="A Stranger", brief="unknown to the world")},
    )
    assert scene_refusal(draft, world) == (
        "the scene needs at least one existing cast member brought back"
    )


def test_a_dead_draft_cast_member_is_refused() -> None:
    world = small_world().payload.world
    ghost = EntityId("ghost")
    draft = _draft(
        present=("mira",), cast={ghost: Npc(id=ghost, name="Ghost", brief="", alive=False)}
    )
    assert scene_refusal(draft, world) == (
        "the scene needs cast members as the worldsmith may write them: alive: ['ghost']"
    )


def test_a_hidden_multi_word_name_in_situation_is_refused() -> None:
    world = small_world().payload.world
    stalker = EntityId("stalker")
    told = f"{SITUATION} Old Man Riley waits by the dumpster."
    draft = _draft(
        situation=told,
        present=("mira",),
        hidden=(stalker,),
        cast={stalker: Npc(id=stalker, name="Old Man Riley", brief="")},
    )
    assert scene_refusal(draft, world) == (
        "the scene needs a situation that does not name what is hidden: ['Old Man Riley']"
    )


def test_install_scene_appends_a_run_and_returns_the_opened_fact() -> None:
    game = small_world()
    facts = install_scene(game, _draft(present=("mira",)))
    assert len(game.payload.world.runs) == 2
    assert facts == (
        Fact(
            kind="scene_opened",
            trace="the story moves to The Alley",
            told=True,
            card="New scene: The Alley",
        ),
    )


def test_render_worldsmith_lists_the_player_first() -> None:
    prompt = render_worldsmith(
        small_world().payload.world, "Explore the alley.", "guidance text", SceneDraft
    )
    assert prompt.index("Jax[player]") < prompt.index("Mira[mira]")


def _return_draft(*, offers: int = 2) -> ReturnDraft:
    return ReturnDraft.model_validate(
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
        }
    )


def test_a_return_naming_an_unmet_cast_member_in_the_debrief_is_refused() -> None:
    world = hub_world().payload.world
    stranger = EntityId("stranger")
    world.cast[stranger] = Npc(id=stranger, name="Old Man Riley", brief="", known=False)
    draft = _return_draft().model_copy(update={"debrief": "Old Man Riley saw them off with a nod."})
    assert scene_refusal(draft, world) == (
        "the scene needs a debrief that does not name what the player has not met: "
        "['Old Man Riley']"
    )


def test_install_scene_on_a_return_swaps_the_board_and_notes_nothing() -> None:
    for finished in (True, False):
        game = hub_world()
        game.payload.world.run.job_done = finished
        facts = install_scene(game, _return_draft())
        world = game.payload.world
        assert [offer.title for offer in world.board] == ["Job 1", "Job 2"]
        assert [fact.kind for fact in facts] == ["job_closed", "scene_opened"]
        assert game.notes == ()


def test_install_scene_on_a_hub_draft_lands_a_home_card() -> None:
    game = hub_world()
    facts = install_scene(game, _return_draft())
    assert any(fact.card == "Home: Back at the Camp" for fact in facts)


def _opening(**fields: object) -> SceneDraft:
    return _draft(
        place=HUB_PLACE,
        present=("keeper",),
        cast={"keeper": Npc(id=EntityId("keeper"), name="Keeper", brief="Holds the camp")},
        **fields,
    )


def test_opening_canon_sets_the_hub_and_board_for_a_campaign_only() -> None:
    offers = [{"title": "A", "pitch": "Take A."}, {"title": "B", "pitch": "Take B."}]
    campaign = opening_canon(
        HubDraft.model_validate({**_opening().model_dump(), "offers": offers}), source=""
    )
    assert campaign.hub == HUB_PLACE
    assert [offer.title for offer in campaign.board] == ["A", "B"]
    assert opening_canon(_opening(), source="").hub is None
