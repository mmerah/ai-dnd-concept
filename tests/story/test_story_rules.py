from random import Random

from story_test_support import initial_story_game, setback_direction

from aidm.actions import TakeItem
from aidm.base import PLAYER_ID, EntityId
from aidm.engines.story.access import item_state, player_state
from aidm.engines.story.direction import StoryConsequence, StoryDirection, dump_direction
from aidm.engines.story.state import StoryGearTag, StoryItemState


def test_story_risk_is_seeded_pure_and_commits_once() -> None:
    engine, state = initial_story_game()
    before = state.model_dump_json()
    direction = dump_direction(setback_direction(take_stress=True))

    transition = engine.resolve(direction, state, Random(2))

    assert transition == engine.resolve(direction, state, Random(2))
    assert state.model_dump_json() == before
    assert [fact.kind for fact in transition.facts] == [
        "risk_rolled",
        "growth_marked",
        "stress_changed",
    ]
    rolled = transition.facts[0]
    assert rolled.data["dice"] == [1, 1]
    assert rolled.data["outcome"] == "setback"
    safe = rolled.narrator
    assert safe == "Kael's attempt ends in a setback"
    assert safe is not None and all(private not in safe for private in ("1+1", "difficulty"))

    player = player_state(transition.state)
    assert (player.growth_marks, player.stress) == (1, 1)
    engine.validate_state(transition.state)


def test_story_mode_can_take_an_existing_item_and_keep_its_rule_state() -> None:
    # StoryWorld only flushes the entries it hydrated: this proves take_item, which never
    # reads the item's engine rules, still leaves them intact through commit.
    engine, state = initial_story_game()
    gear = StoryGearTag(name="Folded Chart", description="It marks the sealed stair.")
    prepared = state.draft()
    prepared.world.record(EntityId("vault_map"), "item").rules = StoryItemState(
        gear=gear
    ).model_dump(mode="json")
    state = prepared.committed()
    mechanics: list[StoryConsequence] = [TakeItem(item_id=EntityId("vault_map"))]
    direction = dump_direction(
        StoryDirection(
            intent="Kael lifts the map from beneath the flagstone.",
            tone="hushed",
            mechanics=mechanics,
        )
    )

    after = engine.resolve(direction, state, Random(0)).state

    map_item = after.world.require(EntityId("vault_map"))
    assert map_item.known
    assert map_item in after.world.children(PLAYER_ID, "item")
    assert item_state(after.world.record(map_item.id, "item").rules).gear == gear
