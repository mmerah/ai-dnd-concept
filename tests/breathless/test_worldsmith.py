import pytest
from breathless_test_support import (
    HUB_PLACE,
    HUB_SITUATION,
    JOB,
    JOB_PLACE,
    MIRA,
    SITUATION,
    hub_world,
    small_world,
)
from pydantic import BaseModel

from aidm.core.entities import EntityId
from aidm.core.facts import Fact
from aidm.core.model import CheckAnswer
from aidm.engines.breathless.world import Npc
from aidm.engines.breathless.worldsmith import (
    HubDraft,
    SceneDraft,
    apply_scene,
    install_scene,
    opening_canon,
    render_worldsmith,
    scene_refusal,
    write_next,
)
from aidm.engines.core import PLAYER_ID
from aidm.engines.hub import GO_HOME


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
    prompt = render_worldsmith(small_world().payload.world, "Explore the alley.", "guidance text")
    assert prompt.index("Jax[player]") < prompt.index("Mira[mira]")


def _hub_draft(*, finished: bool, offers: int = 2) -> HubDraft:
    return HubDraft.model_validate(
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
            "debrief": {
                "text": "The pharmacy is cleared and the supplies are back.",
                "finished": finished,
            },
        }
    )


async def test_write_next_asks_for_hub_draft_only_on_go_home_away_from_the_hub() -> None:
    game = hub_world()
    recorded: list[type[BaseModel]] = []

    async def answer(prompt: str, model: type[BaseModel], refusal: CheckAnswer) -> BaseModel:
        recorded.append(model)
        written = _hub_draft(finished=True) if model is HubDraft else _draft(present=("keeper",))
        assert refusal(written) is None
        return written

    _ = await write_next({}, game, GO_HOME, answer)
    assert recorded[-1] is HubDraft

    _ = await write_next({}, game, "I look around the pharmacy.", answer)
    assert recorded[-1] is SceneDraft


def test_a_job_scene_placed_at_the_hub_is_refused() -> None:
    world = hub_world().payload.world
    draft = _draft(place=HUB_PLACE, present=("keeper",))
    assert scene_refusal(draft, world) == (
        "the scene needs a place away from the hub: home is reached by going home"
    )


def test_a_return_with_one_offer_is_refused() -> None:
    world = hub_world().payload.world
    assert scene_refusal(_hub_draft(finished=True, offers=1), world, hub=True) == (
        "the scene needs a board of 2 to 3 offers"
    )


def test_a_scene_draft_with_offers_is_refused_off_the_hub() -> None:
    world = hub_world().payload.world
    draft = _draft(
        place=JOB_PLACE, present=("keeper",), offers=[{"title": "A", "pitch": "I take A."}]
    )
    assert scene_refusal(draft, world) == "the scene needs no offers: only the hub has a board"


def test_a_take_written_at_the_hub_without_a_job_is_refused() -> None:
    game = hub_world()
    install_scene(game, _hub_draft(finished=True))
    world = game.payload.world
    draft = _draft(place=JOB_PLACE, present=("keeper",))
    assert scene_refusal(draft, world) == (
        "the scene needs a `job` of a short paragraph: who wants what done, what done looks "
        "like, what it pays"
    )


def test_a_later_job_scene_carrying_a_job_is_refused() -> None:
    world = hub_world().payload.world
    draft = _draft(place=JOB_PLACE, present=("keeper",), job=JOB)
    assert scene_refusal(draft, world) == (
        "the scene needs no `job`: only the scene that leaves the hub carries it"
    )


def test_install_scene_on_a_return_swaps_the_board_and_notes_nothing() -> None:
    for finished in (True, False):
        game = hub_world()
        facts = install_scene(game, _hub_draft(finished=finished))
        world = game.payload.world
        assert [offer.title for offer in world.board] == ["Job 1", "Job 2"]
        assert [fact.kind for fact in facts] == ["job_closed", "scene_opened"]
        assert game.notes == ()


def test_install_scene_on_a_hub_draft_lands_a_home_card() -> None:
    game = hub_world()
    facts = install_scene(game, _hub_draft(finished=True))
    assert any(fact.card == "Home: Back at the Camp" for fact in facts)


def test_render_worldsmith_in_a_campaign_has_the_hub_section() -> None:
    world = hub_world().payload.world
    prompt = render_worldsmith(world, "I look around the camp.", "guidance text")
    assert "THE HUB" in prompt


def test_render_worldsmith_returning_has_the_hub_draft_schema() -> None:
    world = hub_world().payload.world
    prompt = render_worldsmith(world, GO_HOME, "guidance text", returning=True)
    assert '"debrief"' in prompt


def test_render_worldsmith_at_the_hub_has_the_take_brief() -> None:
    game = hub_world()
    install_scene(game, _hub_draft(finished=True))
    world = game.payload.world
    prompt = render_worldsmith(world, "I look at the board.", "guidance text")
    assert "WHAT COMES NEXT is the job they take" in prompt


def _opening(**fields: object) -> SceneDraft:
    return _draft(
        place=HUB_PLACE,
        present=("keeper",),
        cast={"keeper": Npc(id=EntityId("keeper"), name="Keeper", brief="Holds the camp")},
        **fields,
    )


def test_opening_canon_sets_the_hub_and_board_for_a_campaign_only() -> None:
    offers = [{"title": "A", "pitch": "Take A."}, {"title": "B", "pitch": "Take B."}]
    campaign = opening_canon(_opening(offers=offers), source="", kind="campaign")
    assert campaign.hub == HUB_PLACE
    assert [offer.title for offer in campaign.board] == ["A", "B"]
    assert opening_canon(_opening(), source="", kind="one-shot").hub is None
