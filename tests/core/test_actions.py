from collections.abc import Sequence

import pytest
from core_test_support import initialized

from aidm.state import actions
from aidm.state.model import PLAYER_ID, AdvanceThread, Counter, Entity, EntityId, Fact, Game, Thread

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


def _draft() -> Game:
    _, state = initialized()
    return state.draft()


def _kinds(facts: Sequence[Fact]) -> list[str]:
    return [fact.kind for fact in facts]


def test_world_actions_move_and_reveal_only_what_the_player_witnesses() -> None:
    draft = _draft()

    assert actions.reveal(draft, MARA) == []
    assert _kinds(actions.reveal(draft, VAULT_MAP)) == ["entity_discovered"]
    assert _kinds(actions.move(draft, ELENA, STUDY)) == ["entity_discovered", "entity_moved"]
    assert _kinds(actions.move(draft, MARA, VAULT)) == ["entity_moved"]
    assert _kinds(actions.move(draft, PLAYER_ID, CLOISTER)) == ["entity_moved"]

    with pytest.raises(ValueError, match="would not be witnessed"):
        _ = actions.move(draft, ELENA, VAULT)
    with pytest.raises(ValueError, match="is a actor, not a location"):
        _ = actions.move(draft, PLAYER_ID, MARA)
    with pytest.raises(ValueError, match="unknown entity id"):
        _ = actions.reveal(draft, EntityId("ghost"))


def test_movement_walks_unfound_ways_and_stops_at_locked_ones() -> None:
    draft = _draft()

    assert _kinds(actions.move(draft, PLAYER_ID, CLOISTER)) == ["entity_moved"]
    # `cloister`—`bell_tower` is authored unknown both ways: walking it finds it.
    assert _kinds(actions.move(draft, PLAYER_ID, BELL_TOWER)) == [
        "entity_discovered",
        "entity_moved",
    ]
    way = draft.world.require(CLOISTER).exit_to(BELL_TOWER)
    assert way is not None and way.known is True
    back = draft.world.require(BELL_TOWER).exit_to(CLOISTER)
    assert back is not None and back.known is True

    _ = actions.move(draft, PLAYER_ID, CLOISTER)
    # `cloister`—`vault` is authored in world.json already `locked`.
    with pytest.raises(ValueError, match="is locked"):
        _ = actions.move(draft, PLAYER_ID, VAULT)
    _ = actions.unlock_exit(draft, VAULT)
    mirrored = draft.world.require(VAULT).exit_to(CLOISTER)
    assert mirrored is not None and mirrored.locked is False
    assert _kinds(actions.move(draft, PLAYER_ID, VAULT)) == ["entity_discovered", "entity_moved"]


def test_movement_is_refused_where_no_way_is_authored_at_all() -> None:
    """Topology alone decides where the player may walk: an exit-less place strands them."""
    draft = _draft()
    pit = Entity(id=EntityId("oubliette"), kind="location", name="the oubliette", brief="A pit.")
    draft.world.entities.append(pit)
    draft.player.parent_id = pit.id

    with pytest.raises(ValueError, match="no way leads from here"):
        _ = actions.move(draft, PLAYER_ID, STUDY)


def test_a_party_member_travels_with_the_player() -> None:
    draft = _draft()

    joined = actions.join_party(draft, MARA)
    assert _kinds(joined) == ["party_joined"]
    moved = actions.move(draft, PLAYER_ID, CLOISTER)
    assert [fact.data["entity_id"] for fact in moved] == [PLAYER_ID, MARA]

    left = actions.leave_party(draft, MARA)
    assert _kinds(left) == ["party_left"]
    assert _kinds(actions.move(draft, PLAYER_ID, STUDY)) == ["entity_moved"]


def test_inventory_actions_gate_on_position_and_carrying() -> None:
    draft = _draft()

    took = actions.move(draft, VAULT_MAP, PLAYER_ID)[1]
    assert (took.data["entity_id"], took.data["to_id"]) == (VAULT_MAP, PLAYER_ID)
    with pytest.raises(ValueError, match="already carries"):
        _ = actions.move(draft, VAULT_MAP, PLAYER_ID)
    with pytest.raises(ValueError, match="player's own location"):
        _ = actions.move(draft, LANTERN, VAULT)
    (dropped,) = actions.move(draft, LANTERN, STUDY)
    assert (dropped.data["entity_id"], dropped.data["to_kind"]) == (LANTERN, "location")
    (given,) = actions.move(draft, VAULT_MAP, MARA)
    assert (given.data["entity_id"], given.data["to_id"]) == (VAULT_MAP, MARA)
    assert given.trace == "the player gave the item the vault map[vault_map] to the npc Mara[mara]"

    created, carried = actions.improvise(draft, "a rusty key")
    assert created.data["name"] == "a rusty key"
    assert carried.data["entity_id"] == created.data["entity_id"]

    with pytest.raises(ValueError, match="not loose at the player's location"):
        _ = actions.move(draft, VAULT_MAP, PLAYER_ID)
    with pytest.raises(ValueError, match="does not carry"):
        _ = actions.move(draft, VAULT_MAP, STUDY)
    with pytest.raises(ValueError, match="not here with the player"):
        _ = actions.move(draft, LANTERN, TOMAS)


def test_trait_changes_round_trip_and_refuse_what_the_entity_does_not_carry() -> None:
    draft = _draft()

    (added,) = actions.add_trait(draft, PLAYER_ID, "hunted", "watched")
    assert added.data["trait_id"] == "hunted"
    assert draft.player.trait("hunted") is not None

    assert _kinds(actions.remove_trait(draft, PLAYER_ID, "hunted")) == ["trait_removed"]

    with pytest.raises(ValueError, match="carries no trait"):
        _ = actions.remove_trait(draft, PLAYER_ID, "hunted")
    # Kael's character sheet already carries `relic-hunter` as an authored skill.
    with pytest.raises(ValueError, match="already carries the trait"):
        _ = actions.add_trait(draft, PLAYER_ID, "relic-hunter")


def test_acting_on_an_unrevealed_actor_reveals_it_before_its_traits_change() -> None:
    """The leak rule: an actor is revealed by being acted on, an item or a place is not."""
    draft = _draft()
    _ = actions.move(draft, PLAYER_ID, CLOISTER)

    assert _kinds(actions.add_trait(draft, RAT, "hurt")) == ["entity_discovered", "trait_added"]


def test_a_tick_fills_the_threads_clock_and_stops_at_its_maximum() -> None:
    draft = _draft()
    draft.world.threads.append(
        Thread(id="ritual", title="The rite", clock=Counter(current=0, maximum=2))
    )

    for filled in (1, 2, 2):
        moved = actions.advance_thread(draft, AdvanceThread(thread_id="ritual", tick=1))
        assert moved[0].data["clock_current"] == filled

    (renoted,) = actions.advance_thread(
        draft, AdvanceThread(thread_id="ritual", status="resolved", note="the rite is complete")
    )
    ritual = draft.world.thread("ritual")
    assert ritual is not None and ritual.note == "the rite is complete"
    assert renoted.trace.endswith("— note: the rite is complete")


def test_a_tick_on_a_thread_without_a_clock_is_refused() -> None:
    draft = _draft()
    with pytest.raises(ValueError, match="no clock to tick"):
        _ = actions.advance_thread(draft, AdvanceThread(thread_id="vault-seal", tick=1))
