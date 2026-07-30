import pytest
from aidm.domain.base import EntityId
from aidm.domain.definitions import ScenarioDefinition
from aidm.domain.direction import DirectionRecord, require_direction
from aidm.domain.engine import (
    DependencyStamp,
    EngineData,
    EngineRef,
    EngineStamp,
    require_envelope,
)
from aidm.domain.events import RuleEvent
from aidm.domain.reducer import apply_one
from aidm.domain.state import GameState, WorldState
from aidm.engine_api.contracts import EngineDescriptor
from aidm.engine_api.registry import EngineRegistry
from aidm.utils.models import updated
from core_test_support import (
    DESCRIPTOR,
    RULES_CODEC,
    STAMP,
    initialized,
    scenario,
)
from core_test_support import (
    TestEngine as _TestEngine,
)
from pydantic import ValidationError


def _data(engine: str = "test-engine", schema_version: int = 1) -> EngineData:
    return EngineData.model_validate(
        {
            "engine": engine,
            "schema_version": schema_version,
            "payload": {},
        }
    )


def test_engine_codec_rejects_the_wrong_engine_and_schema() -> None:
    with pytest.raises(ValueError, match="codec expects 'test-engine'"):
        RULES_CODEC.decode(_data(engine="other-engine"))
    with pytest.raises(ValueError, match="codec expects 1"):
        RULES_CODEC.decode(_data(schema_version=2))


def test_engine_envelopes_and_directions_require_the_selected_stamp() -> None:
    with pytest.raises(ValueError, match="selected engine"):
        require_envelope(_data(engine="other-engine"), STAMP, "test payload")
    with pytest.raises(ValueError, match="selected engine schema_version"):
        require_envelope(_data(schema_version=2), STAMP, "test payload")

    wrong_direction = DirectionRecord(
        engine="other-engine",
        schema_version=1,
        intent="Wait.",
        tone="quiet",
        speaker_id=None,
        mechanics=(),
    )
    with pytest.raises(ValueError, match="direction record engine"):
        require_direction(wrong_direction, STAMP)
    with pytest.raises(ValidationError):
        DirectionRecord.model_validate(
            {
                "engine": "test-engine",
                "schema_version": 0,
                "intent": "Wait.",
                "tone": "quiet",
                "speaker_id": None,
                "mechanics": [],
            }
        )


def test_registry_rejects_duplicate_missing_and_misregistered_engines() -> None:
    registry = EngineRegistry()
    registry.register(DESCRIPTOR, _TestEngine)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(DESCRIPTOR, _TestEngine)
    with pytest.raises(ValueError, match="not installed"):
        registry.require(EngineRef(id="missing", rules_version=1))

    wrong = EngineRegistry()
    descriptor = EngineDescriptor(
        ref=DESCRIPTOR.ref,
        schema_version=DESCRIPTOR.schema_version + 1,
    )
    wrong.register(descriptor, _TestEngine)
    with pytest.raises(ValueError, match="does not match registration"):
        wrong.require(descriptor.ref)


@pytest.mark.parametrize(
    ("engine", "schema_version", "message"),
    [
        ("other-engine", 1, "rule event engine"),
        ("test-engine", 2, "rule event schema"),
    ],
)
def test_reducer_rejects_wrong_rule_event_stamps(
    engine: str,
    schema_version: int,
    message: str,
) -> None:
    selected, state = initialized()
    event = RuleEvent(
        engine=engine,
        schema_version=schema_version,
        name="test-event",
        payload={},
    )

    with pytest.raises(ValueError, match=message):
        apply_one(state, event, selected.rules)


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


def test_scenario_topology_and_dependency_stamps_are_normalized() -> None:
    with pytest.raises(ValidationError, match="starting_location_id"):
        updated(scenario(), starting_location_id=EntityId("missing"))

    duplicate = DependencyStamp(kind="content-pack", id="srd", version="1")
    with pytest.raises(ValidationError, match="duplicate"):
        EngineStamp(
            id="test-engine",
            rules_version=1,
            schema_version=1,
            dependencies=(duplicate, duplicate),
        )
    with pytest.raises(ValidationError, match="sorted"):
        EngineStamp(
            id="test-engine",
            rules_version=1,
            schema_version=1,
            dependencies=(
                DependencyStamp(kind="z-pack", id="z", version="1"),
                DependencyStamp(kind="a-pack", id="a", version="1"),
            ),
        )

    restored = ScenarioDefinition.model_validate_json(scenario().model_dump_json())
    assert restored == scenario()


def test_game_state_rejects_a_rules_envelope_from_another_engine() -> None:
    _, state = initialized()
    with pytest.raises(ValidationError, match="game rules engine"):
        GameState.model_validate(
            state.model_dump(round_trip=True) | {"rules": _data(engine="other-engine")}
        )
