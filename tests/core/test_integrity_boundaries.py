import pytest
from core_test_support import initialized, scenario
from pydantic import ValidationError

from aidm.domain.base import EntityId
from aidm.domain.definitions import ScenarioDefinition
from aidm.domain.engine import EngineData
from aidm.domain.events import RuleEvent
from aidm.domain.reducer import apply_one
from aidm.domain.state import GameState, WorldState
from aidm.utils.models import updated
from aidm_story.codecs import ACTOR_STATE_CODEC


def _foreign_data() -> EngineData:
    return EngineData.model_validate({"engine": "dnd5e", "schema_version": 1, "payload": {}})


def test_engine_codec_rejects_the_wrong_engine_and_schema() -> None:
    """The codecs are the only remaining check on an engine payload's schema_version."""
    _, state = initialized()
    assert state.player.rules is not None

    with pytest.raises(ValueError, match="codec expects 'story'"):
        ACTOR_STATE_CODEC.decode(_foreign_data())
    with pytest.raises(ValueError, match="codec expects 1"):
        ACTOR_STATE_CODEC.decode(updated(state.player.rules, schema_version=2))


def test_reducer_rejects_a_rule_event_from_another_engine() -> None:
    engine, state = initialized()
    event = RuleEvent(engine="dnd5e", schema_version=1, name="test-event", payload={})

    with pytest.raises(ValueError, match="rule event engine"):
        apply_one(state, event, engine.rules)


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


def test_game_state_rejects_a_rules_envelope_from_another_engine() -> None:
    _, state = initialized()
    with pytest.raises(ValidationError, match="game rules engine"):
        GameState.model_validate(state.model_dump(round_trip=True) | {"rules": _foreign_data()})
