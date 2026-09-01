import pytest
from twentyfourxx_test_support import KESTREL, SABLE, SITUATION, small_world

from aidm.core.entities import EngineId, EntityId
from aidm.core.facts import Fact
from aidm.engines.core import PLAYER_ID
from aidm.engines.twentyfourxx.world import Npc
from aidm.engines.twentyfourxx.worldsmith import (
    SceneDraft,
    apply_scene,
    build_scenario,
    install_scene,
    opening_canon,
    render_worldsmith,
    scene_refusal,
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
    canon = opening_canon(draft, source="")
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
