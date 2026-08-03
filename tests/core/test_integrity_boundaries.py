from random import Random

import pytest
from core_test_support import STORY, initialized, scenario, updated, with_entity
from pydantic import ValidationError

from aidm.actions import TakeItem
from aidm.base import PLAYER_ID, EngineId, EntityId, ItemEntity, LocationEntity
from aidm.content import (
    Character,
    CharacterOverlay,
    CharacterProfile,
    Scenario,
    ScenarioOverlay,
    ScenarioWorld,
)
from aidm.engines.dnd5e.state import Dnd5eActorState, StatBlock
from aidm.engines.story.state import (
    DEFAULT_APPROACHES,
    StoryCharacterData,
    StoryGearTag,
    StoryItemDefinition,
)
from aidm.transition import Direction
from aidm.world import ScenarioMeta, WorldState

HELD = EntityId("frayed_rope")
UNHELD = EntityId("silk_rope")


def _character(*, holds: ItemEntity, gear_for: EntityId) -> Character:
    return Character(
        id="test-character",
        engine=STORY,
        profile=CharacterProfile(
            name="Test Character",
            brief="A character built only for this test.",
            items=(holds,),
        ),
        overlay=CharacterOverlay(
            character=StoryCharacterData(approaches=DEFAULT_APPROACHES).model_dump(mode="json"),
            entities={
                gear_for: StoryItemDefinition(
                    gear=StoryGearTag(name="Silk Rope", description="Braided silk.")
                ).model_dump(mode="json")
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


def test_a_record_may_not_hold_another_engines_payload() -> None:
    """The gate has to fire on a resumed save too, not only on the turn that wrote the payload."""
    engine, state = initialized()
    draft = state.draft()
    draft.world.actor(PLAYER_ID).rules = Dnd5eActorState(stats=StatBlock()).model_dump(mode="json")

    engine.validate_state(state)
    with pytest.raises(ValidationError):
        engine.validate_state(draft.committed())


def test_a_direction_from_another_engine_is_refused() -> None:
    """Core actions validate under either engine, so only the tag can reject a foreign direction."""
    engine, state = initialized()
    foreign = Direction(
        engine=EngineId("dnd5e"),
        intent="Kael reaches for the map.",
        tone="tense",
        mechanics=[TakeItem(item_id=EntityId("vault_map")).model_dump(mode="json")],
    )

    with pytest.raises(ValueError, match="received a 'dnd5e' direction"):
        engine.resolve(foreign, state, Random(0))


def test_scenario_topology_is_validated() -> None:
    with pytest.raises(ValidationError, match="starting_location_id"):
        updated(scenario().world, starting_location_id=EntityId("missing"))


def test_an_overlay_may_not_name_an_entity_the_author_never_wrote() -> None:
    """An overlay keys off authored ids, so a typo must fail at load, not go silently unread."""
    with pytest.raises(ValidationError, match="is not authored"):
        _character(holds=_rope(HELD), gear_for=UNHELD)


def test_an_overlay_may_not_name_a_location() -> None:
    """Core still owns which kinds bear rules; only Phase B gives a location a payload."""
    where = EntityId("study")
    world = ScenarioWorld(
        meta=ScenarioMeta(title="A Room", premise="Only a room."),
        starting_location_id=where,
        entities=(LocationEntity(id=where, name="Study", brief="A cramped room.", known=True),),
    )
    with pytest.raises(ValidationError, match="is a location and takes no rules"):
        Scenario(
            id="test-scenario",
            engine=STORY,
            world=world,
            overlay=ScenarioOverlay(entities={where: {}}),
        )


def test_a_character_knows_the_gear_they_start_with() -> None:
    """Unknown carried gear would be hidden canon inside the inventory the Narrator is shown."""
    with pytest.raises(ValidationError, match="knows the gear they start with"):
        _character(holds=_rope(HELD, known=False), gear_for=HELD)
