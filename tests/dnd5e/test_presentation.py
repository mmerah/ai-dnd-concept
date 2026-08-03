from fivee_test_support import initial_5e_game

from aidm.base import ActorEntity, EntityId
from aidm.engine import entity_renderer
from aidm.prompts import SceneSnapshot, VisibleScene, render_narrator


def test_5e_presentation_exposes_full_state_for_every_visible_actor() -> None:
    engine, state = initial_5e_game()
    mara = state.world.require_kind(EntityId("mara"), ActorEntity)

    describe = entity_renderer(engine, state)
    player_state = describe(state.player)
    npc_state = describe(mara)

    assert "hp 11/11" in player_state
    assert "ac 10" in player_state
    assert "advancement: not awarded" in player_state
    assert "hp 4/4" in npc_state
    assert "ac 10" in npc_state

    prompt = render_narrator(
        VisibleScene.of(SceneSnapshot.of(state)),
        describe,
        state.scenario,
        intent="Mara watches Kael.",
        tone="wary",
        speaker_id=None,
        evidence="- nothing changes",
        prompt="I study Mara.",
    )
    assert "Mara[id=mara]" in prompt
    assert "hp 4/4" in prompt
    assert "ac 10" in prompt
    assert "srd-2014/gear/lantern-hooded" in prompt
    assert '"weight":2.0' in prompt
    assert "Elena" not in prompt
