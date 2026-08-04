from random import Random

from core_test_support import tool_context, turn_context
from story_test_support import initial_story_game, setback

from aidm.base import PLAYER_ID, EntityId
from aidm.engines.story.state import StoryGearTag, StoryItemState, item_state, player_state
from aidm.tools import take_item


def test_story_risk_is_seeded_pure_and_commits_once() -> None:
    engine, state = initial_story_game()
    before = state.model_dump_json()

    after, facts = setback(engine, state, stress=True)

    assert (after, facts) == setback(engine, state, stress=True)
    assert state.model_dump_json() == before
    assert [fact.kind for fact in facts] == ["risk_rolled", "growth_marked", "stress_changed"]
    rolled = facts[0]
    assert rolled.data["dice"] == [1, 1]
    assert rolled.data["outcome"] == "setback"
    safe = rolled.narrator
    assert safe == "Kael's attempt ends in a setback"
    assert safe is not None and all(private not in safe for private in ("1+1", "difficulty"))

    player = player_state(after)
    assert (player.growth_marks, player.stress) == (1, 1)
    engine.validate_state(after)


def test_story_mode_can_take_an_existing_item_and_keep_its_rule_state() -> None:
    """A core tool never reads the item's engine rules; commit must leave them intact anyway."""
    engine, state = initial_story_game()
    gear = StoryGearTag(name="Folded Chart", description="It marks the sealed stair.")
    prepared = state.draft()
    prepared.world.record(EntityId("vault_map"), "item").rules = StoryItemState(
        gear=gear
    ).model_dump(mode="json")
    context = turn_context(engine, prepared.committed(), Random(0))

    _ = take_item(tool_context(context), EntityId("vault_map"))
    after = context.draft.committed()

    map_item = after.world.require(EntityId("vault_map"))
    assert map_item.known
    assert map_item in after.world.children(PLAYER_ID, "item")
    assert item_state(after.world.record(map_item.id, "item").rules).gear == gear
