from fivee_test_support import initial_5e_game

from aidm.base import PLAYER_ID, ActorEntity, EntityId
from aidm.engine import entity_renderer
from aidm.engines.dnd5e.facts import AttackRolled, HpChanged
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


def test_5e_narrator_fact_translates_committed_mechanics() -> None:
    hp = HpChanged(target_id=EntityId("mara"), target_name="Mara", delta=-2, wounds="hurt")
    attack = AttackRolled(
        actor_name="Kael",
        target_name="Mara",
        weapon="sword",
        roll=11,
        total=15,
        ac=13,
        hit=True,
    )

    assert hp.narrator_summary == "Mara is hurt"
    assert attack.narrator_summary == "Kael's attack hits Mara"
    assert "vs ac 13" in attack.trace_summary


def test_5e_narrator_may_receive_the_players_hp_delta() -> None:
    hp = HpChanged(target_id=PLAYER_ID, target_name="Kael", delta=-2, wounds="hurt")

    assert hp.narrator_summary == "hp -2"
