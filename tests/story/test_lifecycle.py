from aidm.domain.base import EntityId
from aidm.domain.definitions import (
    CharacterDefinition,
    LocationDefinition,
    ScenarioDefinition,
    ScenarioMeta,
    StartingItemDefinition,
)
from aidm.domain.state import world_from_definitions
from aidm_story.constants import ENGINE_ID
from aidm_story.lifecycle import StoryLifecycle
from aidm_story.models import (
    DEFAULT_APPROACHES,
    StoryCharacterData,
    StoryGearTag,
    StoryItemDefinition,
)


def _gear_item(name: str, gear_name: str) -> StartingItemDefinition:
    return StartingItemDefinition(
        name=name,
        brief=name,
        engine_data=StoryItemDefinition(gear=StoryGearTag(name=gear_name, description=gear_name)),
    )


def test_each_starting_item_keeps_its_own_gear_even_when_names_collide() -> None:
    """Core slugs a repeated name apart, so the engine must key off the id core assigned."""
    scenario = ScenarioDefinition(
        meta=ScenarioMeta(title="Test scenario", premise="A place to test in."),
        engine=ENGINE_ID,
        starting_location_id=EntityId("hall"),
        entities=(LocationDefinition(id=EntityId("hall"), name="Hall", brief="A bare hall."),),
    )
    character = CharacterDefinition(
        name="Test Character",
        brief="A character built only for this test.",
        engine_data=StoryCharacterData(approaches=DEFAULT_APPROACHES),
        starting_items=(_gear_item("rope", "Frayed Rope"), _gear_item("rope", "Silk Rope")),
    )
    authored = world_from_definitions(scenario, character)

    initialized = StoryLifecycle.initialise(authored, character.engine_data)

    ropes = [entity for entity in authored.world.entities.values() if entity.name == "rope"]
    gear = [initialized.item(entity.id).gear for entity in ropes]
    assert [tag.name for tag in gear if tag is not None] == ["Frayed Rope", "Silk Rope"]
