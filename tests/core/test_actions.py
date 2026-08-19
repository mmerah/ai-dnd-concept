from collections.abc import Sequence

import pytest
from core_test_support import initialized

from aidm.state import actions
from aidm.state.base import PLAYER_ID, Counter, Entity, EntityId
from aidm.state.facts import Fact
from aidm.state.hooks import MAX_HOOK_ROUNDS, fire_hooks
from aidm.state.world import CONNECTED, PARTY_MEMBER, AdvanceThread, GameState, Hook, Thread

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


def _draft() -> GameState:
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
    hidden = actions.relation_change(draft, "remove", CONNECTED, CLOISTER, VAULT)
    assert hidden[0].narrator is None, "a hidden tie's trace names an unmet place"

    with pytest.raises(ValueError, match="would not be witnessed"):
        _ = actions.move(draft, ELENA, VAULT)
    with pytest.raises(ValueError, match="is a actor, not a location"):
        _ = actions.move(draft, PLAYER_ID, MARA)
    with pytest.raises(ValueError, match="unknown entity id"):
        _ = actions.reveal(draft, EntityId("ghost"))


def test_movement_follows_the_connections_the_world_authors() -> None:
    draft = _draft()

    assert _kinds(actions.move(draft, PLAYER_ID, CLOISTER)) == ["entity_moved"]
    with pytest.raises(ValueError, match="has not found the way to the bell tower"):
        _ = actions.move(draft, PLAYER_ID, BELL_TOWER)
    revealed = actions.relation_change(draft, "reveal", CONNECTED, CLOISTER, BELL_TOWER)
    assert _kinds(revealed) == ["entity_discovered", "relation_revealed"]
    assert _kinds(actions.move(draft, PLAYER_ID, BELL_TOWER)) == ["entity_moved"]

    _ = actions.move(draft, PLAYER_ID, CLOISTER)
    # `cloister`—`vault` is authored in world.json already `locked`.
    _ = actions.relation_change(draft, "reveal", CONNECTED, CLOISTER, VAULT)
    with pytest.raises(ValueError, match="is locked"):
        _ = actions.move(draft, PLAYER_ID, VAULT)
    _ = actions.relation_change(draft, "unlock", CONNECTED, CLOISTER, VAULT)
    assert _kinds(actions.move(draft, PLAYER_ID, VAULT)) == ["entity_moved"]


def test_movement_is_refused_where_no_way_is_authored_at_all() -> None:
    """Topology alone decides where the player may walk: an exit-less place strands them."""
    draft = _draft()
    pit = Entity(id=EntityId("oubliette"), kind="location", name="the oubliette", brief="A pit.")
    draft.world.entities[pit.id] = pit
    draft.player.parent_id = pit.id

    with pytest.raises(ValueError, match="no way leads from here"):
        _ = actions.move(draft, PLAYER_ID, STUDY)


def test_a_party_member_travels_with_the_player() -> None:
    draft = _draft()

    joined = actions.relation_change(draft, "add", PARTY_MEMBER, MARA, PLAYER_ID)
    assert _kinds(joined) == ["relation_added"]
    moved = actions.move(draft, PLAYER_ID, CLOISTER)
    assert [fact.data["entity_id"] for fact in moved] == [PLAYER_ID, MARA]

    left = actions.relation_change(draft, "remove", PARTY_MEMBER, MARA, PLAYER_ID)
    assert _kinds(left) == ["relation_removed"]
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
    draft.world.threads["ritual"] = Thread(
        id="ritual", title="The rite", clock=Counter(current=0, maximum=2)
    )

    for filled in (1, 2, 2):
        moved = actions.advance_thread(draft, AdvanceThread(thread_id="ritual", tick=1))
        assert moved[0].data["clock_current"] == filled


def test_a_tick_on_a_thread_without_a_clock_is_refused() -> None:
    draft = _draft()
    with pytest.raises(ValueError, match="no clock to tick"):
        _ = actions.advance_thread(draft, AdvanceThread(thread_id="vault-seal", tick=1))


def test_a_hook_reveals_and_advances_its_thread_when_its_entity_is_discovered() -> None:
    draft = _draft()
    draft.world.hooks = {
        "chart-read": Hook(
            id="chart-read",
            on_discover=VAULT_MAP,
            reveals=(ELENA,),
            advance_thread=AdvanceThread(thread_id="vault-seal", stage="rite-known"),
            note="the archivist is close",
        ),
    }

    fired = fire_hooks(draft, actions.reveal(draft, VAULT_MAP))

    assert _kinds(fired) == ["hook_fired", "entity_discovered", "thread_advanced"]
    assert draft.world.fired_hooks == ("chart-read",)
    assert draft.world.pending_notes == ("the archivist is close",)
    assert draft.world.threads["vault-seal"].stage == "rite-known"


def test_a_hook_that_cannot_apply_lands_as_hook_failed() -> None:
    draft = _draft()
    draft.world.hooks = {
        "broken": Hook(id="broken", on_discover=VAULT_MAP, reveals=(EntityId("ghost"),)),
    }

    fired = fire_hooks(draft, actions.reveal(draft, VAULT_MAP))

    assert _kinds(fired) == ["hook_fired", "hook_failed"]


def test_hooks_that_feed_each_other_stop_at_the_round_cap() -> None:
    """A hook's own reveal fires the hook waiting on it, so a chain is bounded, not endless."""
    draft = _draft()
    chain = ((VAULT_MAP, ELENA), (ELENA, VAULT), (VAULT, BELL_TOWER), (BELL_TOWER, RAT))
    draft.world.hooks = {
        f"link-{number}": Hook(id=f"link-{number}", on_discover=seen, reveals=(revealed,))
        for number, (seen, revealed) in enumerate(chain)
    }

    fired = fire_hooks(draft, actions.reveal(draft, VAULT_MAP))

    assert fired[-1].kind == "hooks_capped"
    assert sum(1 for fact in fired if fact.kind == "hook_fired") == MAX_HOOK_ROUNDS
