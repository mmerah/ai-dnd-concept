import pytest
from core_test_support import initialized, scenario, updated, with_entity
from pydantic import ValidationError

from aidm.base import PLAYER_ID, EntityId, ItemEntity, LocationEntity
from aidm.content import Character, CharacterOverlay, CharacterProfile
from aidm.engines.dnd5e.state import Dnd5eActorState, StatBlock
from aidm.engines.story.state import (
    DEFAULT_APPROACHES,
    StoryCharacterData,
    StoryGearTag,
    StoryItemDefinition,
)
from aidm.world import WorldState

HELD = EntityId("frayed_rope")
UNHELD = EntityId("silk_rope")


def _character(*, holds: ItemEntity, gear_for: EntityId) -> Character:
    return Character(
        id="test-character",
        engine="story",
        profile=CharacterProfile(
            name="Test Character",
            brief="A character built only for this test.",
            items=(holds,),
        ),
        overlay=CharacterOverlay(
            character=StoryCharacterData(approaches=DEFAULT_APPROACHES),
            items={
                gear_for: StoryItemDefinition(
                    gear=StoryGearTag(name="Silk Rope", description="Braided silk.")
                )
            },
        ),
    )


def _rope(item_id: EntityId, *, known: bool = True) -> ItemEntity:
    return ItemEntity(
        id=item_id, name="rope", brief="A length of rope.", known=known, container_id=PLAYER_ID
    )


def test_world_and_game_state_reject_inconsistent_topology() -> None:
    _, state = initialized()
    player_record = state.world.actor(PLAYER_ID)
    with pytest.raises(ValidationError, match="keys disagree"):
        WorldState.model_validate(
            {"actors": {"wrong-key": player_record.model_dump(round_trip=True)}}
        )

    location = state.world.require_kind(state.player.location_id, LocationEntity)
    same_id_location = updated(location, id=PLAYER_ID)
    with pytest.raises(ValidationError, match="more than one kind"):
        WorldState.model_validate(
            {
                "actors": {PLAYER_ID: player_record.model_dump(round_trip=True)},
                "locations": {PLAYER_ID: same_id_location.model_dump(round_trip=True)},
            }
        )

    with pytest.raises(ValidationError, match="player entity must be known"):
        with_entity(state, updated(state.player, known=False))

    with pytest.raises(ValidationError, match="not in a valid location"):
        with_entity(state, updated(state.player, location_id=EntityId("missing")))


def test_a_record_may_not_hold_another_engines_rules() -> None:
    """A record pairs an entity with its rules, so a missing counterpart cannot be built; a
    foreign engine tag is the only way the two halves can still disagree."""
    _, state = initialized()
    draft = state.draft()
    draft.world.actor(PLAYER_ID).rules = Dnd5eActorState(stats=StatBlock())
    with pytest.raises(ValidationError, match="records hold rules from another engine"):
        draft.committed()


def test_scenario_topology_is_validated() -> None:
    with pytest.raises(ValidationError, match="starting_location_id"):
        updated(scenario().world, starting_location_id=EntityId("missing"))


def test_an_overlay_may_not_name_an_entity_the_author_never_wrote() -> None:
    """An overlay keys off authored ids, so a typo must fail at load, not go silently unread."""
    with pytest.raises(ValidationError, match="no authored item"):
        _character(holds=_rope(HELD), gear_for=UNHELD)


def test_a_character_knows_the_gear_they_start_with() -> None:
    """Unknown carried gear would be hidden canon inside the inventory the Narrator is shown."""
    with pytest.raises(ValidationError, match="knows the gear they start with"):
        _character(holds=_rope(HELD, known=False), gear_for=HELD)
