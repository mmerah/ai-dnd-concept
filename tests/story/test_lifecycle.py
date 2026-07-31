import pytest

from aidm.domain.base import EntityId
from aidm.domain.definitions import CharacterDefinition, ScenarioDefinition, ScenarioMeta
from aidm.domain.entities import LocationDefinition, StartingItemDefinition
from aidm.domain.state import world_from_definitions
from aidm_story.codecs import CHARACTER_CODEC, ITEM_DEFINITION_CODEC, ITEM_STATE_CODEC
from aidm_story.constants import ENGINE_REF
from aidm_story.lifecycle import StoryLifecycle
from aidm_story.models import (
    DEFAULT_APPROACHES,
    StoryCharacterData,
    StoryGearTag,
    StoryItemDefinition,
)


def _scenario() -> ScenarioDefinition:
    return ScenarioDefinition(
        meta=ScenarioMeta(title="Test scenario", premise="A place to test in."),
        engine=ENGINE_REF,
        starting_location_id=EntityId("hall"),
        entities=(LocationDefinition(id=EntityId("hall"), name="Hall", brief="A bare hall."),),
    )


def _gear_item(name: str, gear_name: str) -> StartingItemDefinition:
    return StartingItemDefinition(
        name=name,
        brief=name,
        engine_data=ITEM_DEFINITION_CODEC.encode(
            StoryItemDefinition(gear=StoryGearTag(name=gear_name, description=gear_name))
        ),
    )


def _character(starting_items: tuple[StartingItemDefinition, ...]) -> CharacterDefinition:
    return CharacterDefinition(
        name="Test Character",
        brief="A character built only for this test.",
        engine=ENGINE_REF,
        engine_data=CHARACTER_CODEC.encode(StoryCharacterData(approaches=DEFAULT_APPROACHES)),
        starting_items=starting_items,
    )


def test_starting_items_are_matched_by_name_not_by_position() -> None:
    # F53: declare the items in the opposite order from how core happens to place them in
    # the world, so a position-based match would attach each item's gear to the other one.
    lantern = _gear_item("lantern", "Lantern Gear")
    rope = _gear_item("rope", "Rope Gear")
    scenario = _scenario()
    character = _character((rope, lantern))
    world = world_from_definitions(scenario, character)

    initialized = StoryLifecycle().initialise(world, scenario, character)

    lantern_id = next(entity.id for entity in world.entities.values() if entity.name == "lantern")
    rope_id = next(entity.id for entity in world.entities.values() if entity.name == "rope")
    lantern_rules = initialized.entity_rules[lantern_id]
    rope_rules = initialized.entity_rules[rope_id]
    assert lantern_rules is not None and rope_rules is not None
    lantern_gear = ITEM_STATE_CODEC.decode(lantern_rules).gear
    rope_gear = ITEM_STATE_CODEC.decode(rope_rules).gear
    assert lantern_gear is not None and lantern_gear.name == "Lantern Gear"
    assert rope_gear is not None and rope_gear.name == "Rope Gear"


def test_initialise_fails_fast_on_an_unmatched_starting_item() -> None:
    # Simulates core drift: the world was built without a starting item that the
    # character definition still lists, instead of silently dropping its engine_data.
    matched = _gear_item("lantern", "Lantern Gear")
    unmatched = _gear_item("spare rope", "Spare Rope Gear")
    scenario = _scenario()
    world = world_from_definitions(scenario, _character((matched,)))

    with pytest.raises(ValueError, match="unmatched starting items"):
        StoryLifecycle().initialise(world, scenario, _character((matched, unmatched)))
