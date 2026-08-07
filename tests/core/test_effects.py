import pytest
from core_test_support import initialized

from aidm.state.apply import apply_effect
from aidm.state.base import PLAYER_ID, EntityId
from aidm.state.effects import (
    AddRelation,
    AddTag,
    AdjustCounter,
    Effect,
    GainImprovisedItem,
    GrantCounter,
    MoveActor,
    MoveItem,
    RemoveRelation,
    RemoveTag,
    Reveal,
    RevealRelation,
    SetNote,
    SetNumber,
    SpendCounter,
    TagRelation,
    UntagRelation,
)
from aidm.state.facts import Fact
from aidm.state.world import CONNECTED, LOCKED_TAG, PARTY_MEMBER, sheet_of

BELL_TOWER = EntityId("bell_tower")
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
    assert turn.kinds(MoveActor(location_id=CLOISTER)) == ["entity_moved"]

    with pytest.raises(ValueError, match="would not be witnessed"):
        _ = turn(MoveActor(location_id=VAULT, entity_id=ELENA))
    with pytest.raises(ValueError, match="is a actor, not a location"):
        _ = turn(MoveActor(location_id=MARA))
    with pytest.raises(ValueError, match="unknown entity id"):
        _ = turn(Reveal(entity_id=EntityId("ghost")))


def test_movement_follows_the_connections_the_world_authors() -> None:
    turn = Applied()

    assert turn.kinds(MoveActor(location_id=CLOISTER)) == ["entity_moved"]
    with pytest.raises(ValueError, match="the player can reach: the abbot's study"):
        _ = turn(MoveActor(location_id=BELL_TOWER))
    revealed = RevealRelation(kind=CONNECTED, source=CLOISTER, target=BELL_TOWER)
    assert turn.kinds(revealed) == ["entity_discovered", "relation_revealed"]
    assert turn.kinds(MoveActor(location_id=BELL_TOWER)) == ["entity_moved"]

    _ = turn(MoveActor(location_id=CLOISTER))
    barred = TagRelation(kind=CONNECTED, source=CLOISTER, target=VAULT, tag="barred", why="rubble")
    assert turn(barred)[0].narrator is None, "a hidden tie's trace names an unmet place"
    _ = turn(RevealRelation(kind=CONNECTED, source=CLOISTER, target=VAULT))
    with pytest.raises(ValueError, match="is locked"):
        _ = turn(MoveActor(location_id=VAULT))
    _ = turn(UntagRelation(kind=CONNECTED, source=CLOISTER, target=VAULT, tag=LOCKED_TAG))
    assert turn.kinds(MoveActor(location_id=VAULT)) == ["entity_moved"]


def test_a_party_member_travels_with_the_player() -> None:
    turn = Applied()

    joined = AddRelation(kind=PARTY_MEMBER, source=MARA, target=PLAYER_ID, why="Mara comes along")
    assert turn.kinds(joined) == ["relation_added"]
    moved = turn(MoveActor(location_id=CLOISTER))
    assert [fact.data["entity_id"] for fact in moved] == [PLAYER_ID, MARA]

    assert turn.kinds(RemoveRelation(kind=PARTY_MEMBER, source=MARA, target=PLAYER_ID)) == [
        "relation_removed"
    ]
    assert turn.kinds(MoveActor(location_id=STUDY)) == ["entity_moved"]


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
    stress = AdjustCounter(entity_id=PLAYER_ID, counter="stress", delta=99, why="the strain")

    (changed,) = turn(stress)
    assert changed.data["delta"] == 5
    assert sheet_of(turn.draft, PLAYER_ID).counters["stress"].current == 5
    assert turn(stress) == []

    (spent,) = turn(SpendCounter(entity_id=PLAYER_ID, counter="stress", amount=2))
    assert spent.data["current"] == 3

    with pytest.raises(ValueError, match="cannot go below"):
        _ = turn(SpendCounter(entity_id=PLAYER_ID, counter="growth", amount=1))
    with pytest.raises(ValueError, match="has no counter"):
        _ = turn(AdjustCounter(entity_id=PLAYER_ID, counter="mana", delta=1, why="x"))


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

    hurt = turn.kinds(AdjustCounter(entity_id=RAT, counter="stress", delta=1, why="the lantern"))

    assert hurt == ["entity_discovered", "counter_changed"]


def test_one_union_two_surfaces_each_refusing_what_the_other_owns() -> None:
    turn = Applied()
    grant = GrantCounter(entity_id=PLAYER_ID, counter="favour", current=1, maximum=1, why="a boon")

    with pytest.raises(ValueError, match="belongs to advancement"):
        _ = turn(grant)
    with pytest.raises(ValueError, match="only advancement raises a maximum"):
        _ = turn(AdjustCounter(entity_id=PLAYER_ID, counter="stress", delta=1, maximum=9))

    def advancing(effect: Effect) -> list[Fact]:
        return apply_effect(turn.draft, effect, turn.engine.default_rules, advancing=True)

    with pytest.raises(ValueError, match="advancement writes only the sheet"):
        _ = advancing(MoveActor(location_id=CLOISTER))
    with pytest.raises(ValueError, match="advancement writes 'player'"):
        _ = advancing(AddTag(entity_id=MARA, tag_id="sworn", why="a promise"))

    _ = advancing(grant)
    _ = advancing(SetNumber(entity_id=PLAYER_ID, key="mana", value=1, why="a new number"))
    sheet = sheet_of(turn.draft, PLAYER_ID)
    assert (sheet.counters["favour"].current, sheet.numbers["mana"]) == (1, 1)
