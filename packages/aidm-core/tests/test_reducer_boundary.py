import pytest
from aidm.domain.base import PLAYER_ID, EntityId
from aidm.domain.definitions import ScenarioMeta
from aidm.domain.engine import EngineData, EngineStamp
from aidm.domain.entities import ActorEntity, LocationEntity
from aidm.domain.events import RuleEvent, RuleStatePatch
from aidm.domain.reducer import apply
from aidm.domain.state import GameState, WorldState


class PatchRules:
    def __init__(self, patch: RuleStatePatch) -> None:
        self.patch = patch

    def apply(self, state: GameState, event: RuleEvent) -> RuleStatePatch:
        return self.patch

    def validate_state(self, state: GameState) -> None:
        return None


def game() -> GameState:
    rules = EngineData(engine="test-engine", schema_version=1, payload={})
    location = LocationEntity(
        id=EntityId("room"),
        name="Room",
        brief="A room.",
        known=True,
    )
    player = ActorEntity(
        id=PLAYER_ID,
        name="Player",
        brief="Here.",
        known=True,
        location_id=location.id,
        rules=rules,
    )
    return GameState(
        engine=EngineStamp(id="test-engine", rules_version=1, schema_version=1),
        scenario=ScenarioMeta(title="Test", premise="Test"),
        world=WorldState(entities={location.id: location, player.id: player}),
        rules=rules,
    )


def test_rule_patch_can_change_only_rules_fields() -> None:
    before = game()
    changed = EngineData(
        engine="test-engine",
        schema_version=1,
        payload={"value": 1},
    )
    event = RuleEvent(
        engine="test-engine",
        schema_version=1,
        name="test-event",
        payload={},
    )

    after = apply(
        before,
        [event],
        PatchRules(RuleStatePatch(entity_rules={PLAYER_ID: changed})),
    )

    assert after.player.rules == changed
    assert after.player.location_id == before.player.location_id
    assert after.world.entities.keys() == before.world.entities.keys()
    assert after.history == before.history
    assert after.turn == before.turn


def test_rule_patch_rejects_unknown_entity_ids() -> None:
    event = RuleEvent(
        engine="test-engine",
        schema_version=1,
        name="bad-patch",
        payload={},
    )
    with pytest.raises(ValueError, match="unknown entity"):
        apply(
            game(),
            [event],
            PatchRules(
                RuleStatePatch(
                    entity_rules={
                        EntityId("missing"): EngineData(
                            engine="test-engine",
                            schema_version=1,
                            payload={},
                        )
                    }
                )
            ),
        )
