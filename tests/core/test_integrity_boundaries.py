import pytest
from core_test_support import initialized, scenario
from pydantic import ValidationError

from aidm.domain.base import EntityId
from aidm.domain.definitions import ScenarioDefinition
from aidm.domain.events import RuleEvent
from aidm.domain.reducer import apply_one
from aidm.domain.state import WorldState
from aidm.utils.models import updated
from aidm_story.constants import ENGINE_ID, SCHEMA_VERSION


def test_reducer_rejects_a_rule_event_from_another_engine() -> None:
    engine, state = initialized()
    event = RuleEvent(engine="dnd5e", schema_version=1, name="test-event", payload={})

    with pytest.raises(ValueError, match="rule event engine"):
        apply_one(state, event, engine.rules)


def test_a_rule_event_from_another_payload_schema_is_refused() -> None:
    """The decoder is the only guard left on `schema_version`; a stale payload must not decode."""
    engine, state = initialized()
    event = RuleEvent(
        engine=ENGINE_ID,
        schema_version=SCHEMA_VERSION + 1,
        name="taken-out",
        payload={"actor_id": "player", "actor_name": "Kael"},
    )

    with pytest.raises(ValueError, match="event schema"):
        engine.rules.apply(state, event)


def test_world_and_game_state_reject_inconsistent_topology() -> None:
    _, state = initialized()
    with pytest.raises(ValidationError, match="keys disagree"):
        WorldState.model_validate(
            {"entities": {"wrong-key": state.player.model_dump(round_trip=True)}}
        )

    hidden_player = updated(state.player, known=False)
    with pytest.raises(ValidationError, match="player entity must be known"):
        updated(state, world=state.world.replacing(hidden_player))

    invalid_location = updated(state.player, location_id=EntityId("missing"))
    with pytest.raises(ValidationError, match="not in a valid location"):
        updated(state, world=state.world.replacing(invalid_location))


def test_scenario_topology_is_validated_and_round_trips() -> None:
    with pytest.raises(ValidationError, match="starting_location_id"):
        updated(scenario(), starting_location_id=EntityId("missing"))

    restored = ScenarioDefinition.model_validate_json(scenario().model_dump_json())
    assert restored == scenario()
