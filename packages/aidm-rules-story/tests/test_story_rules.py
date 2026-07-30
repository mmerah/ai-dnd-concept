import json
from random import Random

import pytest
from aidm.domain.actions import DropItem, TakeItem
from aidm.domain.base import PLAYER_ID, EntityId
from aidm.domain.direction import DirectionRecord
from aidm.domain.events import RuleEvent
from aidm.domain.reducer import apply
from aidm_story.codecs import ACTOR_STATE_CODEC
from aidm_story.direction import HelpfulGear, Risk, StoryConsequence, StoryDirection
from aidm_story.events import decode_story_event
from story_test_support import initial_story_game, setback_direction


def test_story_trace_direction_serializes_frozen_mechanics() -> None:
    engine, _ = initial_story_game()
    direction = DirectionRecord.model_validate(
        {
            "engine": "story",
            "schema_version": 1,
            "intent": "Take a risk.",
            "tone": "tense",
            "speaker_id": None,
            "mechanics": [{"action": "risk", "details": {"difficulty": 2}}],
        }
    )

    assert json.loads(engine.presentation.trace_direction(direction)) == [
        {"action": "risk", "details": {"difficulty": 2}}
    ]


def test_story_risk_is_seeded_pure_and_applies_through_core() -> None:
    engine, state = initial_story_game()
    before = state.model_dump_json()
    direction = setback_direction(take_stress=True)

    events = engine.rules.resolve(direction, state, Random(2))

    assert events == engine.rules.resolve(direction, state, Random(2))
    assert state.model_dump_json() == before
    assert [event.name if isinstance(event, RuleEvent) else event.type for event in events] == [
        "risk-rolled",
        "growth-marked",
        "stress-changed",
    ]
    rolled = events[0]
    assert isinstance(rolled, RuleEvent)
    typed = decode_story_event(rolled, "story", 1)
    assert typed.type == "risk-rolled"
    assert typed.dice == (1, 1)
    assert typed.outcome == "setback"
    safe = engine.presentation.narrator_event(rolled)
    assert safe == "Kael's attempt ends in a setback"
    assert all(private not in safe for private in ("1+1", "difficulty", "modifier"))

    after = apply(state, events, engine.rules)
    assert after.player.rules is not None
    player = ACTOR_STATE_CODEC.decode(after.player.rules)
    assert (player.growth_marks, player.stress) == (1, 1)
    engine.rules.validate_state(after)


def test_dropped_story_gear_cannot_grant_a_risk_bonus() -> None:
    engine, state = initial_story_game()
    (gear,) = state.world.carried_by(PLAYER_ID)
    drop = StoryDirection(
        intent="Kael puts down the lantern.",
        tone="quiet",
        mechanics=[DropItem(item_id=gear.id)],
    )
    dropped = apply(
        state,
        engine.rules.resolve(drop, state, Random(0)),
        engine.rules,
    )
    mechanics: list[StoryConsequence] = [
        Risk(
            approach="clever",
            difficulty=0,
            helpful=HelpfulGear(item_id=gear.id),
        )
    ]
    risk = StoryDirection(
        intent="Kael searches by the lantern's light.",
        tone="uncertain",
        mechanics=mechanics,
    )

    with pytest.raises(ValueError, match="not carried"):
        engine.rules.resolve(risk, dropped, Random(0))


def test_story_mode_can_take_an_existing_item_and_keep_its_rule_state() -> None:
    engine, state = initial_story_game()
    mechanics: list[StoryConsequence] = [TakeItem(item_id=EntityId("vault_map"))]
    direction = StoryDirection(
        intent="Kael lifts the map from beneath the flagstone.",
        tone="hushed",
        mechanics=mechanics,
    )

    after = apply(
        state,
        engine.rules.resolve(direction, state, Random(0)),
        engine.rules,
    )

    map_item = after.world.require(EntityId("vault_map"))
    assert map_item.known
    assert map_item in after.world.carried_by(PLAYER_ID)
    assert map_item.rules is not None
