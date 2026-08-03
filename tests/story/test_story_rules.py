import json
from random import Random

import pytest
from story_test_support import initial_story_game, setback_direction

from aidm.actions import DropItem, TakeItem
from aidm.base import PLAYER_ID, EntityId
from aidm.engines.story.access import item_of, player_rules
from aidm.engines.story.direction import HelpfulGear, Risk, StoryConsequence, StoryDirection
from aidm.engines.story.facts import RiskRolled
from aidm.engines.story.state import StoryGearTag, StoryItemState


def test_story_trace_direction_serializes_typed_mechanics() -> None:
    engine, _ = initial_story_game()
    direction = StoryDirection(
        intent="Take a risk.",
        tone="tense",
        mechanics=[Risk(approach="bold", difficulty=2)],
    )

    assert json.loads(engine.presentation.trace_direction(direction)) == [
        {
            "action": "risk",
            "actor_id": None,
            "approach": "bold",
            "difficulty": 2,
            "helpful": None,
            "hindering": None,
            "on_strong": [],
            "on_mixed": [],
            "on_setback": [],
        }
    ]


def test_story_risk_is_seeded_pure_and_commits_once() -> None:
    engine, state = initial_story_game()
    before = state.model_dump_json()
    direction = setback_direction(take_stress=True)

    transition = engine.rules.resolve(direction, state, Random(2))

    assert transition == engine.rules.resolve(direction, state, Random(2))
    assert state.model_dump_json() == before
    assert [fact.fact for fact in transition.facts] == [
        "risk-rolled",
        "growth-marked",
        "stress-changed",
    ]
    rolled = transition.facts[0]
    assert isinstance(rolled, RiskRolled)
    assert rolled.dice == (1, 1)
    assert rolled.outcome == "setback"
    safe = rolled.narrator_summary
    assert safe == "Kael's attempt ends in a setback"
    assert all(private not in safe for private in ("1+1", "difficulty", "modifier"))

    player = player_rules(transition.state)
    assert (player.growth_marks, player.stress) == (1, 1)
    engine.validate_state(transition.state)


def test_dropped_story_gear_cannot_grant_a_risk_bonus() -> None:
    engine, state = initial_story_game()
    (gear,) = state.world.carried_by(PLAYER_ID)
    drop = StoryDirection(
        intent="Kael puts down the lantern.",
        tone="quiet",
        mechanics=[DropItem(item_id=gear.entity.id)],
    )
    dropped = engine.rules.resolve(drop, state, Random(0)).state
    mechanics: list[StoryConsequence] = [
        Risk(
            approach="clever",
            difficulty=0,
            helpful=HelpfulGear(item_id=gear.entity.id),
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
    gear = StoryGearTag(name="Folded Chart", description="It marks the sealed stair.")
    prepared = state.draft()
    prepared.world.item(EntityId("vault_map")).rules = StoryItemState(gear=gear)
    state = prepared.committed()
    mechanics: list[StoryConsequence] = [TakeItem(item_id=EntityId("vault_map"))]
    direction = StoryDirection(
        intent="Kael lifts the map from beneath the flagstone.",
        tone="hushed",
        mechanics=mechanics,
    )

    after = engine.rules.resolve(direction, state, Random(0)).state

    map_item = after.world.require(EntityId("vault_map"))
    assert map_item.known
    assert map_item in tuple(record.entity for record in after.world.carried_by(PLAYER_ID))
    assert item_of(after, map_item.id)[1].gear == gear
