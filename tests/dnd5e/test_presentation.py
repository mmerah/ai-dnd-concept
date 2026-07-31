from fivee_test_support import initial_5e_game, ruleset

from aidm.agents.context import NarratorContext, build_narrator_scene
from aidm.agents.prompting import build_narrator_prompt
from aidm.domain.base import EntityId
from aidm.domain.entities import ActorEntity
from aidm_5e.domain.models.base import PLAYER_ID as LEGACY_PLAYER_ID
from aidm_5e.domain.models.base import EntityId as LegacyEntityId
from aidm_5e.domain.models.events import AttackRolled, HpChanged
from aidm_5e.events import encode_dnd5e_event
from aidm_5e.factory import dnd5e_engine


def test_5e_presentation_exposes_full_state_for_every_visible_actor() -> None:
    engine, state = initial_5e_game()
    mara = state.world.require_kind(EntityId("mara"), ActorEntity)

    player_state = engine.presentation.entity_state(state.player)
    npc_state = engine.presentation.entity_state(mara)

    assert "hp 11/11" in player_state
    assert "ac 10" in player_state
    assert "advancement: not awarded" in player_state
    assert "hp 4/4" in npc_state
    assert "ac 10" in npc_state

    prompt = build_narrator_prompt(
        NarratorContext(
            scene=build_narrator_scene(state, engine.presentation.entity_state),
            scenario_title=state.scenario.title,
            scenario_premise=state.scenario.premise,
            intent="Mara watches Kael.",
            tone="wary",
            speaker_id=None,
            evidence="- nothing changes",
            prompt="I study Mara.",
        )
    )
    assert "Mara[id=mara]" in prompt
    assert "hp 4/4" in prompt
    assert "ac 10" in prompt
    assert "srd-2014/gear/lantern-hooded" in prompt
    assert '"weight":2.0' in prompt
    assert "Elena" not in prompt


def test_5e_narrator_event_translates_committed_mechanics() -> None:
    presentation = dnd5e_engine(ruleset()).presentation
    hp = encode_dnd5e_event(
        HpChanged(
            target_id=LegacyEntityId("mara"),
            target_name="Mara",
            delta=-2,
            wounds="hurt",
        ),
        "dnd5e",
        1,
    )
    attack = encode_dnd5e_event(
        AttackRolled(
            actor_name="Kael",
            target_name="Mara",
            weapon="sword",
            roll=11,
            total=15,
            ac=13,
            hit=True,
        ),
        "dnd5e",
        1,
    )

    assert presentation.narrator_event(hp) == "Mara is hurt"
    assert presentation.narrator_event(attack) == "Kael's attack hits Mara"
    assert "vs ac 13" in presentation.trace_event(attack)


def test_5e_narrator_may_receive_the_players_hp_delta() -> None:
    presentation = dnd5e_engine(ruleset()).presentation
    hp = encode_dnd5e_event(
        HpChanged(
            target_id=LEGACY_PLAYER_ID,
            target_name="Kael",
            delta=-2,
            wounds="hurt",
        ),
        "dnd5e",
        1,
    )

    assert presentation.narrator_event(hp) == "hp -2"
