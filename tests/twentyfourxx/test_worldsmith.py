import pytest
from pydantic import BaseModel
from twentyfourxx_test_support import (
    HUB_PLACE,
    HUB_SITUATION,
    JOB_PLACE,
    KESTREL,
    SABLE,
    SITUATION,
    hub_world,
    small_world,
)

from aidm.core.entities import EngineId, EntityId
from aidm.core.facts import Fact
from aidm.core.model import CheckAnswer
from aidm.engines.core import PLAYER_ID
from aidm.engines.hub import GO_HOME
from aidm.engines.twentyfourxx.world import Npc
from aidm.engines.twentyfourxx.worldsmith import (
    BOARD_GUIDANCE,
    HubDraft,
    SceneDraft,
    apply_scene,
    build_scenario,
    install_scene,
    opening_canon,
    render_worldsmith,
    scene_refusal,
    write_next,
)


def _draft(**fields: object) -> SceneDraft:
    base = {
        "place": "bay-office",
        "title": "The Bay Office",
        "question": "Can they slip past the night crew before the lights return?",
        "situation": SITUATION,
    }
    return SceneDraft.model_validate({**base, **fields})


def test_apply_scene_drops_the_player_from_present() -> None:
    world = small_world().payload.world
    apply_scene(world, _draft(present=("Kestrel", "sable")))
    assert PLAYER_ID not in world.run.present
    assert SABLE in world.run.present


def test_apply_scene_resolves_present_by_id_too() -> None:
    world = small_world().payload.world
    apply_scene(world, _draft(present=(str(SABLE),)))
    assert SABLE in world.run.present


def test_apply_scene_marks_present_cast_known() -> None:
    world = small_world().payload.world
    apply_scene(world, _draft(present=("sable",)))
    assert world.cast[SABLE].known is True


def test_apply_scene_lands_new_cast() -> None:
    world = small_world().payload.world
    stranger = EntityId("stranger")
    apply_scene(
        world,
        _draft(
            present=("kestrel", "stranger"),
            cast={stranger: Npc(id=stranger, name="A Stranger", brief="unknown to the world")},
        ),
    )
    assert stranger in world.cast


def test_apply_scene_refuses_a_draft_cast_entry_under_player_id() -> None:
    world = small_world().payload.world
    draft = _draft(
        cast={PLAYER_ID: Npc(id=PLAYER_ID, name="Someone", brief="filed wrongly", known=True)}
    )
    with pytest.raises(ValueError, match="rewrites the player"):
        apply_scene(world, draft)


def test_apply_scene_refuses_rewriting_an_existing_cast_member() -> None:
    world = small_world().payload.world
    draft = _draft(
        present=("kestrel",),
        cast={KESTREL: Npc(id=KESTREL, name="Kestrel", brief="rewritten")},
    )
    with pytest.raises(ValueError, match="already in the cast"):
        apply_scene(world, draft)


def test_apply_scene_refuses_a_misfiled_cast_entry() -> None:
    world = small_world().payload.world
    stranger = EntityId("stranger")
    other = EntityId("other")
    draft = _draft(
        present=("stranger",),
        cast={stranger: Npc(id=other, name="A Stranger", brief="filed wrongly")},
    )
    with pytest.raises(ValueError, match="is filed under"):
        apply_scene(world, draft)


def test_apply_scene_refuses_present_hidden_overlap() -> None:
    world = small_world().payload.world
    with pytest.raises(ValueError, match="both present and hidden"):
        apply_scene(world, _draft(present=("kestrel",), hidden=("kestrel",)))


def test_apply_scene_refuses_hiding_someone_met() -> None:
    world = small_world().payload.world
    with pytest.raises(ValueError, match="already met"):
        apply_scene(world, _draft(hidden=("kestrel",)))


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
        present=("kestrel",), cast={ghost: Npc(id=ghost, name="Ghost", brief="", alive=False)}
    )
    assert scene_refusal(draft, world) == (
        "the scene needs cast members as the worldsmith may write them: alive: ['ghost']"
    )


def test_a_hidden_multi_word_name_in_situation_is_refused() -> None:
    world = small_world().payload.world
    stalker = EntityId("stalker")
    told = f"{SITUATION} Old Man Riley waits by the containers."
    draft = _draft(
        situation=told,
        present=("kestrel",),
        hidden=(stalker,),
        cast={stalker: Npc(id=stalker, name="Old Man Riley", brief="")},
    )
    assert scene_refusal(draft, world) == (
        "the scene needs a situation that does not name what is hidden: ['Old Man Riley']"
    )


def test_a_draft_naming_the_player_in_present_drops_the_entry() -> None:
    world = small_world().payload.world
    apply_scene(world, _draft(present=("kestrel", "player")))
    assert PLAYER_ID not in world.run.present
    assert KESTREL in world.run.present


def test_install_scene_appends_a_run_and_returns_the_opened_fact() -> None:
    game = small_world()
    facts = install_scene(game, _draft(present=("kestrel",)))
    assert len(game.payload.world.runs) == 2
    assert facts == (
        Fact(
            kind="scene_opened",
            trace="the story moves to The Bay Office",
            told=True,
            card="New scene: The Bay Office",
        ),
    )


def test_render_worldsmith_lists_the_player_first() -> None:
    prompt = render_worldsmith(small_world().payload.world, "Explore the bay.", "guidance text")
    assert prompt.index("Rook[player]") < prompt.index("Kestrel[kestrel]")


def test_opening_canon_marks_present_known() -> None:
    stranger = EntityId("stranger")
    draft = _draft(
        present=(stranger,),
        cast={stranger: Npc(id=stranger, name="A Stranger", brief="new to the world")},
    )
    canon = opening_canon(draft, source="", kind="one-shot")
    assert canon.cast[stranger].known is True


def test_build_scenario_refuses_an_unmet_draft() -> None:
    with pytest.raises(ValueError, match="cast member besides the player"):
        build_scenario("Loading Bay", "", "", (), _draft(), source="", kind="one-shot")


def test_build_scenario_stamps_the_engine_id() -> None:
    stranger = EntityId("stranger")
    draft = _draft(
        present=(stranger,),
        cast={stranger: Npc(id=stranger, name="A Stranger", brief="new to the world")},
    )
    scenario = build_scenario("Loading Bay", "", "", (), draft, source="", kind="one-shot")
    assert scenario.engine == EngineId("twentyfourxx")


def _hub_draft(*, finished: bool, offers: int = 2) -> HubDraft:
    return HubDraft.model_validate(
        {
            "place": HUB_PLACE,
            "title": "Back at the Amber Tap",
            "question": "What does Kael do next, now the job is behind them?",
            "situation": HUB_SITUATION,
            "present": ("fixer",),
            "offers": [
                {"title": f"Job {number}", "pitch": f"I take job {number}."}
                for number in range(1, offers + 1)
            ],
            "debrief": {"text": "The crates are cleared and paid for.", "finished": finished},
        }
    )


async def test_write_next_asks_for_hub_draft_only_on_go_home_away_from_the_hub() -> None:
    game = hub_world()
    recorded: list[type[BaseModel]] = []

    async def answer(prompt: str, model: type[BaseModel], refusal: CheckAnswer) -> BaseModel:
        recorded.append(model)
        written = _hub_draft(finished=True) if model is HubDraft else _draft(present=("fixer",))
        assert refusal(written) is None
        return written

    _ = await write_next({}, game, GO_HOME, answer)
    assert recorded[-1] is HubDraft

    _ = await write_next({}, game, "I look around the warehouse.", answer)
    assert recorded[-1] is SceneDraft


def test_a_job_scene_placed_at_the_hub_is_refused() -> None:
    world = hub_world().payload.world
    draft = _draft(place=HUB_PLACE, present=("fixer",))
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
        place=JOB_PLACE, present=("fixer",), offers=[{"title": "A", "pitch": "I take A."}]
    )
    assert scene_refusal(draft, world) == "the scene needs no offers: only the hub has a board"


def test_install_scene_on_a_finished_hub_draft_swaps_the_board_and_notes_the_job() -> None:
    game = hub_world()
    facts = install_scene(game, _hub_draft(finished=True))
    world = game.payload.world
    assert [offer.title for offer in world.board] == ["Job 1", "Job 2"]
    assert [fact.kind for fact in facts] == ["job_closed", "scene_opened"]
    assert any("The Dock Run" in note for note in game.notes)


def test_install_scene_on_an_open_hub_draft_skips_the_note() -> None:
    game = hub_world()
    facts = install_scene(game, _hub_draft(finished=False))
    assert [fact.kind for fact in facts] == ["job_closed", "scene_opened"]
    assert game.notes == ()


def test_render_worldsmith_in_a_campaign_has_the_hub_section() -> None:
    world = hub_world().payload.world
    prompt = render_worldsmith(world, "I look around the bar.", "guidance text")
    assert "THE HUB" in prompt


def test_render_worldsmith_returning_has_the_hub_draft_schema_and_board_guidance() -> None:
    world = hub_world().payload.world
    prompt = render_worldsmith(world, GO_HOME, "guidance text", returning=True)
    assert '"debrief"' in prompt
    assert BOARD_GUIDANCE in prompt
