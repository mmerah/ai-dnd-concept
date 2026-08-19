import pytest
from core_test_support import initialized

from aidm.state.apply_effects import apply_effect
from aidm.state.base import PLAYER_ID, Counter, Entity, EntityId
from aidm.state.effects import (
    AdvanceThread,
    GainImprovisedItem,
    Move,
    RelationChange,
    Reveal,
    TraitChange,
    WorldOp,
)
from aidm.state.facts import Fact
from aidm.state.hooks import MAX_HOOK_ROUNDS, fire_hooks
from aidm.state.world import CONNECTED, PARTY_MEMBER, Hook, Thread

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
        _, state = initialized()
        self.draft = state.draft()

    def __call__(self, effect: WorldOp) -> list[Fact]:
        return apply_effect(self.draft, effect)

    def kinds(self, effect: WorldOp) -> list[str]:
        return [fact.kind for fact in self(effect)]


def test_world_effects_move_and_reveal_only_what_the_player_witnesses() -> None:
    turn = Applied()

    assert turn(Reveal(entity_id=MARA)) == []
    assert turn.kinds(Reveal(entity_id=VAULT_MAP)) == ["entity_discovered"]
    arrived = Move(to_id=STUDY, entity_id=ELENA)
    assert turn.kinds(arrived) == ["entity_discovered", "entity_moved"]
    assert turn.kinds(Move(to_id=VAULT, entity_id=MARA)) == ["entity_moved"]
    assert turn.kinds(Move(entity_id=PLAYER_ID, to_id=CLOISTER)) == ["entity_moved"]
    hidden = RelationChange(mode="remove", kind=CONNECTED, source=CLOISTER, target=VAULT)
    assert turn(hidden)[0].narrator is None, "a hidden tie's trace names an unmet place"

    with pytest.raises(ValueError, match="would not be witnessed"):
        _ = turn(Move(to_id=VAULT, entity_id=ELENA))
    with pytest.raises(ValueError, match="is a actor, not a location"):
        _ = turn(Move(entity_id=PLAYER_ID, to_id=MARA))
    with pytest.raises(ValueError, match="unknown entity id"):
        _ = turn(Reveal(entity_id=EntityId("ghost")))


def test_movement_follows_the_connections_the_world_authors() -> None:
    turn = Applied()

    assert turn.kinds(Move(entity_id=PLAYER_ID, to_id=CLOISTER)) == ["entity_moved"]
    with pytest.raises(ValueError, match="has not found the way to the bell tower"):
        _ = turn(Move(entity_id=PLAYER_ID, to_id=BELL_TOWER))
    revealed = RelationChange(mode="reveal", kind=CONNECTED, source=CLOISTER, target=BELL_TOWER)
    assert turn.kinds(revealed) == ["entity_discovered", "relation_revealed"]
    assert turn.kinds(Move(entity_id=PLAYER_ID, to_id=BELL_TOWER)) == ["entity_moved"]

    _ = turn(Move(entity_id=PLAYER_ID, to_id=CLOISTER))
    # `cloister`—`vault` is authored in world.json already `locked`.
    _ = turn(RelationChange(mode="reveal", kind=CONNECTED, source=CLOISTER, target=VAULT))
    with pytest.raises(ValueError, match="is locked"):
        _ = turn(Move(entity_id=PLAYER_ID, to_id=VAULT))
    _ = turn(RelationChange(mode="unlock", kind=CONNECTED, source=CLOISTER, target=VAULT))
    assert turn.kinds(Move(entity_id=PLAYER_ID, to_id=VAULT)) == ["entity_moved"]


def test_movement_is_refused_where_no_way_is_authored_at_all() -> None:
    """Topology alone decides where the player may walk: an exit-less place strands them."""
    turn = Applied()
    pit = Entity(id=EntityId("oubliette"), kind="location", name="the oubliette", brief="A pit.")
    turn.draft.world.entities[pit.id] = pit
    turn.draft.player.parent_id = pit.id

    with pytest.raises(ValueError, match="no way leads from here"):
        _ = turn(Move(entity_id=PLAYER_ID, to_id=STUDY))


def test_a_party_member_travels_with_the_player() -> None:
    turn = Applied()

    joined = RelationChange(mode="add", kind=PARTY_MEMBER, source=MARA, target=PLAYER_ID)
    assert turn.kinds(joined) == ["relation_added"]
    moved = turn(Move(entity_id=PLAYER_ID, to_id=CLOISTER))
    assert [fact.data["entity_id"] for fact in moved] == [PLAYER_ID, MARA]

    left = RelationChange(mode="remove", kind=PARTY_MEMBER, source=MARA, target=PLAYER_ID)
    assert turn.kinds(left) == ["relation_removed"]
    assert turn.kinds(Move(entity_id=PLAYER_ID, to_id=STUDY)) == ["entity_moved"]


def test_inventory_effects_gate_on_position_and_carrying() -> None:
    turn = Applied()

    took = turn(Move(entity_id=VAULT_MAP, to_id=PLAYER_ID))[1]
    assert (took.data["entity_id"], took.data["to_id"]) == (VAULT_MAP, PLAYER_ID)
    with pytest.raises(ValueError, match="already carries"):
        _ = turn(Move(entity_id=VAULT_MAP, to_id=PLAYER_ID))
    with pytest.raises(ValueError, match="player's own location"):
        _ = turn(Move(entity_id=LANTERN, to_id=VAULT))
    (dropped,) = turn(Move(entity_id=LANTERN, to_id=STUDY))
    assert (dropped.data["entity_id"], dropped.data["to_kind"]) == (LANTERN, "location")
    (given,) = turn(Move(entity_id=VAULT_MAP, to_id=MARA))
    assert (given.data["entity_id"], given.data["to_id"]) == (VAULT_MAP, MARA)

    created, carried = turn(GainImprovisedItem(item_name="a rusty key"))
    assert created.data["name"] == "a rusty key"
    assert carried.data["entity_id"] == created.data["entity_id"]

    with pytest.raises(ValueError, match="not loose at the player's location"):
        _ = turn(Move(entity_id=VAULT_MAP, to_id=PLAYER_ID))
    with pytest.raises(ValueError, match="does not carry"):
        _ = turn(Move(entity_id=VAULT_MAP, to_id=STUDY))
    with pytest.raises(ValueError, match="not here with the player"):
        _ = turn(Move(entity_id=LANTERN, to_id=TOMAS))


def test_trait_changes_round_trip_and_refuse_what_the_entity_does_not_carry() -> None:
    turn = Applied()

    (added,) = turn(TraitChange(mode="add", entity_id=PLAYER_ID, trait_id="hunted", text="watched"))
    assert added.data["trait_id"] == "hunted"
    assert turn.draft.player.trait("hunted") is not None

    removed = TraitChange(mode="remove", entity_id=PLAYER_ID, trait_id="hunted")
    assert turn.kinds(removed) == ["trait_removed"]

    with pytest.raises(ValueError, match="carries no trait"):
        _ = turn(TraitChange(mode="remove", entity_id=PLAYER_ID, trait_id="hunted"))
    # Kael's character sheet already carries `relic-hunter` as an authored skill.
    with pytest.raises(ValueError, match="already carries the trait"):
        _ = turn(TraitChange(mode="add", entity_id=PLAYER_ID, trait_id="relic-hunter"))


def test_acting_on_an_unrevealed_actor_reveals_it_before_its_traits_change() -> None:
    """The leak rule: an actor is revealed by being acted on, an item or a place is not."""
    turn = Applied()
    _ = turn(Move(entity_id=PLAYER_ID, to_id=CLOISTER))

    change = TraitChange(mode="add", entity_id=RAT, trait_id="hurt")
    kinds = turn.kinds(change)

    assert kinds == ["entity_discovered", "trait_added"]


def test_a_tick_fills_the_threads_clock_and_stops_at_its_maximum() -> None:
    _, state = initialized()
    draft = state.draft()
    draft.world.threads["ritual"] = Thread(
        id="ritual", title="The rite", clock=Counter(current=0, maximum=2)
    )

    for filled in (1, 2, 2):
        moved = apply_effect(draft, AdvanceThread(thread_id="ritual", tick=1))
        assert moved[0].data["clock_current"] == filled


def test_a_tick_on_a_thread_without_a_clock_is_refused() -> None:
    turn = Applied()
    with pytest.raises(ValueError, match="no clock to tick"):
        _ = turn(AdvanceThread(thread_id="vault-seal", tick=1))


def test_a_hook_reveals_and_advances_its_thread_when_its_entity_is_discovered() -> None:
    _, state = initialized()
    draft = state.draft()
    draft.world.hooks = {
        "chart-read": Hook(
            id="chart-read",
            on_discover=VAULT_MAP,
            reveals=(ELENA,),
            advance_thread=AdvanceThread(thread_id="vault-seal", stage="rite-known"),
            note="the archivist is close",
        ),
    }

    fired = fire_hooks(draft, apply_effect(draft, Reveal(entity_id=VAULT_MAP)))

    assert [fact.kind for fact in fired] == ["hook_fired", "entity_discovered", "thread_advanced"]
    assert draft.world.fired_hooks == ("chart-read",)
    assert draft.world.pending_notes == ("the archivist is close",)
    assert draft.world.threads["vault-seal"].stage == "rite-known"


def test_a_hook_that_cannot_apply_lands_as_hook_failed() -> None:
    _, state = initialized()
    draft = state.draft()
    draft.world.hooks = {
        "broken": Hook(id="broken", on_discover=VAULT_MAP, reveals=(EntityId("ghost"),)),
    }

    fired = fire_hooks(draft, apply_effect(draft, Reveal(entity_id=VAULT_MAP)))

    assert [fact.kind for fact in fired] == ["hook_fired", "hook_failed"]


def test_hooks_that_feed_each_other_stop_at_the_round_cap() -> None:
    """A hook's own reveal fires the hook waiting on it, so a chain is bounded, not endless."""
    _, state = initialized()
    draft = state.draft()
    chain = ((VAULT_MAP, ELENA), (ELENA, VAULT), (VAULT, BELL_TOWER), (BELL_TOWER, RAT))
    draft.world.hooks = {
        f"link-{number}": Hook(id=f"link-{number}", on_discover=seen, reveals=(revealed,))
        for number, (seen, revealed) in enumerate(chain)
    }

    fired = fire_hooks(draft, apply_effect(draft, Reveal(entity_id=VAULT_MAP)))

    assert fired[-1].kind == "hooks_capped"
    assert sum(1 for fact in fired if fact.kind == "hook_fired") == MAX_HOOK_ROUNDS
