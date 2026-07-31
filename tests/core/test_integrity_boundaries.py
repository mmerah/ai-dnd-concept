import pytest
from core_test_support import initialized, scenario, updated, with_entity
from pydantic import ValidationError

from aidm.domain.base import EntityId
from aidm.domain.definitions import ScenarioDefinition
from aidm.domain.state import WorldState


def test_world_and_game_state_reject_inconsistent_topology() -> None:
    _, state = initialized()
    with pytest.raises(ValidationError, match="keys disagree"):
        WorldState.model_validate(
            {"entities": {"wrong-key": state.player.model_dump(round_trip=True)}}
        )

    with pytest.raises(ValidationError, match="player entity must be known"):
        with_entity(state, updated(state.player, known=False))

    with pytest.raises(ValidationError, match="not in a valid location"):
        with_entity(state, updated(state.player, location_id=EntityId("missing")))


def test_scenario_topology_is_validated_and_round_trips() -> None:
    with pytest.raises(ValidationError, match="starting_location_id"):
        updated(scenario(), starting_location_id=EntityId("missing"))

    restored = ScenarioDefinition.model_validate_json(scenario().model_dump_json())
    assert restored == scenario()
