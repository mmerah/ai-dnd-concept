from fivee_test_support import initial_5e_game, ruleset

from aidm.agents.context import SceneSnapshot, VisibleScene
from aidm.agents.prompting import render_narrator
from aidm.domain.base import PLAYER_ID, EntityId
from aidm.domain.entities import ActorEntity
from aidm.engines import entity_renderer
from aidm_5e.domain.models.facts import AttackRolled, HpChanged
from aidm_5e.factory import dnd5e_engine


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
    presentation = dnd5e_engine(ruleset()).presentation
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

    assert presentation.narrator_fact(hp) == "Mara is hurt"
    assert presentation.narrator_fact(attack) == "Kael's attack hits Mara"
    assert "vs ac 13" in presentation.trace_fact(attack)


def test_5e_narrator_may_receive_the_players_hp_delta() -> None:
    presentation = dnd5e_engine(ruleset()).presentation
    hp = HpChanged(target_id=PLAYER_ID, target_name="Kael", delta=-2, wounds="hurt")

    assert presentation.narrator_fact(hp) == "hp -2"
