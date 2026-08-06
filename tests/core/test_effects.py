import pytest
from core_test_support import initialized

from aidm.core.base import PLAYER_ID, EntityId
from aidm.core.effects import (
    AddTag,
    AdjustCounter,
    Effect,
    GainImprovisedItem,
    MoveActor,
    MoveItem,
    RemoveTag,
    Reveal,
    SetNote,
    SetNumber,
    SpendCounter,
    apply_effect,
)
from aidm.core.facts import Fact
from aidm.core.world import sheet_of

CLOISTER = EntityId("cloister")
STUDY = EntityId("study")
ELENA = EntityId("elena")
LANTERN = EntityId("lantern")
MARA = EntityId("mara")
RAT = EntityId("cloister_rat")
TOMAS = EntityId("tomas")
VAULT = EntityId("vault")
VAULT_MAP = EntityId("vault_map")


class Applied:
    """One turn's draft and the effects landing on it, as a resolver would apply them."""

    def __init__(self) -> None:
        engine, state = initialized()
        self.engine = engine
        self.draft = state.draft()

    def __call__(self, effect: Effect) -> list[Fact]:
        return apply_effect(self.draft, effect, self.engine.default_rules)

    def kinds(self, effect: Effect) -> list[str]:
        return [fact.kind for fact in self(effect)]


def test_world_effects_move_and_reveal_only_what_the_player_witnesses() -> None:
    turn = Applied()

    assert turn(Reveal(entity_id=MARA)) == []
    assert turn.kinds(Reveal(entity_id=VAULT_MAP)) == ["entity_discovered"]
    arrived = MoveActor(location_id=STUDY, entity_id=ELENA)
    assert turn.kinds(arrived) == ["entity_discovered", "entity_moved"]
    assert turn.kinds(MoveActor(location_id=VAULT, entity_id=MARA)) == ["entity_moved"]
    assert turn.kinds(MoveActor(location_id=VAULT)) == ["entity_discovered", "entity_moved"]

    with pytest.raises(ValueError, match="would not be witnessed"):
        _ = turn(MoveActor(location_id=CLOISTER, entity_id=TOMAS))
    with pytest.raises(ValueError, match="is a actor, not a location"):
        _ = turn(MoveActor(location_id=MARA))
    with pytest.raises(ValueError, match="unknown entity id"):
        _ = turn(Reveal(entity_id=EntityId("ghost")))


def test_inventory_effects_gate_on_position_and_carrying() -> None:
    turn = Applied()

    took = turn(MoveItem(item_id=VAULT_MAP))[1]
    assert (took.data["entity_id"], took.data["to_id"]) == (VAULT_MAP, PLAYER_ID)
    with pytest.raises(ValueError, match="already carries"):
        _ = turn(MoveItem(item_id=VAULT_MAP))
    with pytest.raises(ValueError, match="player's own location"):
        _ = turn(MoveItem(item_id=LANTERN, to_id=VAULT))
    (dropped,) = turn(MoveItem(item_id=LANTERN, to_id=STUDY))
    assert (dropped.data["entity_id"], dropped.data["to_kind"]) == (LANTERN, "location")
    (given,) = turn(MoveItem(item_id=VAULT_MAP, to_id=MARA))
    assert (given.data["entity_id"], given.data["to_id"]) == (VAULT_MAP, MARA)

    created, carried = turn(GainImprovisedItem(item_name="a rusty key"))
    assert created.data["name"] == "a rusty key"
    assert carried.data["entity_id"] == created.data["entity_id"]

    with pytest.raises(ValueError, match="not loose at the player's location"):
        _ = turn(MoveItem(item_id=VAULT_MAP))
    with pytest.raises(ValueError, match="does not carry"):
        _ = turn(MoveItem(item_id=VAULT_MAP, to_id=STUDY))
    with pytest.raises(ValueError, match="not here with the player"):
        _ = turn(MoveItem(item_id=LANTERN, to_id=TOMAS))


def test_counter_effects_clamp_what_lands_and_spending_refuses_an_empty_pool() -> None:
    turn = Applied()
    stress = AdjustCounter(entity_id=PLAYER_ID, counter="stress", delta=99, reason="the strain")

    (changed,) = turn(stress)
    assert changed.data["delta"] == 5
    assert sheet_of(turn.draft, PLAYER_ID).counters["stress"].current == 5
    assert turn(stress) == []

    (spent,) = turn(SpendCounter(entity_id=PLAYER_ID, counter="stress", amount=2))
    assert spent.data["current"] == 3

    with pytest.raises(ValueError, match="cannot go below"):
        _ = turn(SpendCounter(entity_id=PLAYER_ID, counter="growth", amount=1))
    with pytest.raises(ValueError, match="has no counter"):
        _ = turn(AdjustCounter(entity_id=PLAYER_ID, counter="mana", delta=1, reason="x"))


def test_sheet_effects_round_trip_and_refuse_what_the_sheet_does_not_hold() -> None:
    turn = Applied()
    sheet = sheet_of(turn.draft, PLAYER_ID)

    (tagged,) = turn(AddTag(entity_id=PLAYER_ID, tag_id="hunted", text="watched"))
    assert tagged.data["tag_id"] == "hunted"
    assert sheet.tag("hunted") is not None
    assert turn.kinds(RemoveTag(entity_id=PLAYER_ID, tag_id="hunted")) == ["tag_removed"]

    (noted,) = turn(SetNote(entity_id=PLAYER_ID, key="watching", text="the vault door"))
    assert noted.narrator is None
    assert sheet.notes["watching"] == "the vault door"
    assert turn.kinds(SetNote(entity_id=PLAYER_ID, key="watching", text="")) == ["note_set"]
    assert turn(SetNote(entity_id=PLAYER_ID, key="watching", text="")) == []

    (numbered,) = turn(SetNumber(entity_id=PLAYER_ID, key="bold", value=3))
    assert (numbered.data["before"], numbered.data["after"]) == (2, 3)

    with pytest.raises(ValueError, match="carries no tag"):
        _ = turn(RemoveTag(entity_id=PLAYER_ID, tag_id="hunted"))
    with pytest.raises(ValueError, match="has no number"):
        _ = turn(SetNumber(entity_id=PLAYER_ID, key="mana", value=1))
    with pytest.raises(ValueError, match="already carries the tag"):
        _ = turn(AddTag(entity_id=PLAYER_ID, tag_id="relic-hunter"))


def test_acting_on_an_unrevealed_actor_reveals_it_before_its_sheet_changes() -> None:
    """The leak rule: an actor is revealed by being acted on, an item or a place is not."""
    turn = Applied()
    _ = turn(MoveActor(location_id=CLOISTER))

    hurt = turn.kinds(AdjustCounter(entity_id=RAT, counter="stress", delta=1, reason="the lantern"))

    assert hurt == ["entity_discovered", "counter_changed"]
