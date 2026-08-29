from collections.abc import Sequence

import pytest
from core_test_support import initialized

from aidm.state import actions
from aidm.state.entities import PLAYER_ID, SLUG_MAX, Entity, EntityId
from aidm.state.facts import Fact
from aidm.state.model import AdvanceThread, Game, Thread

BELL_TOWER = EntityId("bell-tower")
CLOISTER = EntityId("cloister")
STUDY = EntityId("study")
ELENA = EntityId("elena")
LANTERN = EntityId("lantern")
MARA = EntityId("mara")
RAT = EntityId("cloister-rat")
TOMAS = EntityId("tomas")
VAULT = EntityId("vault")
VAULT_MAP = EntityId("vault-map")


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
    # `cloister`—`bell-tower` is authored unknown both ways: walking it finds it.
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
    draft = _draft()
    pit = Entity(id=EntityId("oubliette"), kind="location", name="the oubliette", brief="A pit.")
    draft.world.entities[pit.id] = pit
    draft.player.parent_id = pit.id

    with pytest.raises(ValueError, match="no way leads from here"):
        _ = actions.move(draft, PLAYER_ID, STUDY)


def test_a_party_member_travels_with_the_player() -> None:
    draft = _draft()

    joined = actions.join_party(draft, MARA)
    assert _kinds(joined) == ["party_joined"]
    moved = actions.move(draft, PLAYER_ID, CLOISTER)
    assert [fact.entity_id for fact in moved] == [PLAYER_ID, MARA]

    left = actions.leave_party(draft, MARA)
    assert _kinds(left) == ["party_left"]
    assert _kinds(actions.move(draft, PLAYER_ID, STUDY)) == ["entity_moved"]


def test_inventory_actions_gate_on_position_and_carrying() -> None:
    draft = _draft()

    took = actions.move(draft, VAULT_MAP, PLAYER_ID)[1]
    assert took.entity_id == VAULT_MAP
    assert draft.world.require(VAULT_MAP).parent_id == PLAYER_ID
    with pytest.raises(ValueError, match="already carries"):
        _ = actions.move(draft, VAULT_MAP, PLAYER_ID)
    with pytest.raises(ValueError, match="player's own location"):
        _ = actions.move(draft, LANTERN, VAULT)
    (dropped,) = actions.move(draft, LANTERN, STUDY)
    assert dropped.entity_id == LANTERN
    assert draft.world.require(LANTERN).parent_id == STUDY
    (given,) = actions.move(draft, VAULT_MAP, MARA)
    assert given.entity_id == VAULT_MAP
    assert given.trace == "the player gave the item the vault map[vault-map] to the npc Mara[mara]"

    created, carried = actions.improvise(draft, "a rusty key")
    assert created.entity_id is not None
    assert draft.world.require(created.entity_id).name == "a rusty key"
    assert carried.entity_id == created.entity_id

    long_name = "a length of frayed rope " * 5
    made = actions.improvise(draft, long_name)[0].entity_id
    again = actions.improvise(draft, long_name)[0].entity_id
    assert made is not None and again is not None and made != again
    assert len(made) <= SLUG_MAX and len(again) <= SLUG_MAX

    with pytest.raises(ValueError, match="not loose at the player's location"):
        _ = actions.move(draft, VAULT_MAP, PLAYER_ID)
    with pytest.raises(ValueError, match="does not carry"):
        _ = actions.move(draft, VAULT_MAP, STUDY)
    with pytest.raises(ValueError, match="not here with the player"):
        _ = actions.move(draft, LANTERN, TOMAS)


def test_trait_changes_round_trip_and_refuse_what_the_entity_does_not_carry() -> None:
    draft = _draft()

    (added,) = actions.add_trait(draft, PLAYER_ID, "Hunted", "watched")
    assert "[hunted]" in added.trace
    assert draft.player.trait("hunted") is not None

    assert _kinds(actions.remove_trait(draft, PLAYER_ID, "hunted")) == ["trait_removed"]

    with pytest.raises(ValueError, match="carries no trait"):
        _ = actions.remove_trait(draft, PLAYER_ID, "hunted")
    # Kael's character sheet already carries `relic-hunter` as an authored skill.
    with pytest.raises(ValueError, match="already carries the trait"):
        _ = actions.add_trait(draft, PLAYER_ID, "Relic Hunter")


def test_acting_on_an_unrevealed_actor_reveals_it_before_its_traits_change() -> None:
    draft = _draft()
    _ = actions.move(draft, PLAYER_ID, CLOISTER)

    assert _kinds(actions.add_trait(draft, RAT, "Hurt")) == ["entity_discovered", "trait_added"]


def test_advance_thread_records_the_status_and_the_note_it_moved() -> None:
    draft = _draft()
    draft.world.threads["ritual"] = Thread(id="ritual", title="The rite")

    (renoted,) = actions.advance_thread(
        draft, AdvanceThread(thread_id="ritual", status="resolved", note="the rite is complete")
    )
    ritual = draft.world.thread("ritual")
    assert ritual is not None and ritual.note == "the rite is complete"
    assert renoted.trace.endswith("— note: the rite is complete")


def test_advance_thread_accepts_a_note_only_patch() -> None:
    draft = _draft()
    draft.world.threads["ritual"] = Thread(id="ritual", title="The rite")

    (noted,) = actions.advance_thread(draft, AdvanceThread(thread_id="ritual", note="a quiet clue"))
    ritual = draft.world.thread("ritual")
    assert ritual is not None and ritual.note == "a quiet clue"
    assert noted.trace.endswith("— note: a quiet clue")


def test_a_kill_drops_items_and_party_and_then_refuses_the_dead_actor() -> None:
    draft = _draft()
    _ = actions.move(draft, PLAYER_ID, CLOISTER)
    _ = actions.move(draft, LANTERN, TOMAS)
    _ = actions.join_party(draft, TOMAS)

    assert _kinds(actions.kill(draft, TOMAS)) == ["items_dropped", "actor_killed"]
    assert draft.world.require(TOMAS).trait("dead") is not None
    assert draft.world.require(LANTERN).parent_id == CLOISTER
    assert TOMAS not in draft.world.party

    with pytest.raises(ValueError, match="dead"):
        _ = actions.add_trait(draft, TOMAS, "Hurt")
    _ = draft.committed()

    _ = actions.kill(draft, PLAYER_ID)
    with pytest.raises(ValueError, match="dead"):
        _ = actions.add_trait(draft, PLAYER_ID, "Hurt")
