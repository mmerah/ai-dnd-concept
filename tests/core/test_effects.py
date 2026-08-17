import pytest
from core_test_support import initialized

from aidm.state.apply import MAX_HOOK_ROUNDS, apply_effect, fire_hooks
from aidm.state.base import PLAYER_ID, Counter, EntityId
from aidm.state.effects import (
    AdvanceThread,
    GainImprovisedItem,
    Move,
    RelationChange,
    Reveal,
    TraitChange,
    WorldOp,
)
from aidm.state.facts import CORE, Fact
from aidm.state.world import CONNECTED, LOCKED_TAG, PARTY_MEMBER, Hook, HookMatch, Thread

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
    assert turn.kinds(Move(to_id=CLOISTER)) == ["entity_moved"]
    hidden = RelationChange(mode="remove", kind=CONNECTED, source=CLOISTER, target=VAULT)
    assert turn(hidden)[0].narrator is None, "a hidden tie's trace names an unmet place"

    with pytest.raises(ValueError, match="would not be witnessed"):
        _ = turn(Move(to_id=VAULT, entity_id=ELENA))
    with pytest.raises(ValueError, match="is a actor, not a location"):
        _ = turn(Move(to_id=MARA))
    with pytest.raises(ValueError, match="name it in `to_id`"):
        _ = turn(Move(entity_id=ELENA))
    with pytest.raises(ValueError, match="unknown entity id"):
        _ = turn(Reveal(entity_id=EntityId("ghost")))


def test_movement_follows_the_connections_the_world_authors() -> None:
    turn = Applied()

    assert turn.kinds(Move(to_id=CLOISTER)) == ["entity_moved"]
    with pytest.raises(ValueError, match="has not found the way to the bell tower"):
        _ = turn(Move(to_id=BELL_TOWER))
    revealed = RelationChange(mode="reveal", kind=CONNECTED, source=CLOISTER, target=BELL_TOWER)
    assert turn.kinds(revealed) == ["entity_discovered", "relation_revealed"]
    assert turn.kinds(Move(to_id=BELL_TOWER)) == ["entity_moved"]

    _ = turn(Move(to_id=CLOISTER))
    # `cloister`—`vault` is authored in world.json already carrying the `locked` tag.
    _ = turn(RelationChange(mode="reveal", kind=CONNECTED, source=CLOISTER, target=VAULT))
    with pytest.raises(ValueError, match="is locked"):
        _ = turn(Move(to_id=VAULT))
    with pytest.raises(ValueError, match="belongs to no other mode"):
        _ = RelationChange(mode="untag", kind=CONNECTED, source=CLOISTER, target=VAULT)
    _ = turn(
        RelationChange(mode="untag", kind=CONNECTED, source=CLOISTER, target=VAULT, tag=LOCKED_TAG)
    )
    assert turn.kinds(Move(to_id=VAULT)) == ["entity_moved"]


def test_a_party_member_travels_with_the_player() -> None:
    turn = Applied()

    joined = RelationChange(mode="add", kind=PARTY_MEMBER, source=MARA, target=PLAYER_ID)
    assert turn.kinds(joined) == ["relation_added"]
    moved = turn(Move(to_id=CLOISTER))
    assert [fact.data["entity_id"] for fact in moved] == [PLAYER_ID, MARA]

    left = RelationChange(mode="remove", kind=PARTY_MEMBER, source=MARA, target=PLAYER_ID)
    assert turn.kinds(left) == ["relation_removed"]
    assert turn.kinds(Move(to_id=STUDY)) == ["entity_moved"]


def test_inventory_effects_gate_on_position_and_carrying() -> None:
    turn = Applied()

    took = turn(Move(entity_id=VAULT_MAP))[1]
    assert (took.data["entity_id"], took.data["to_id"]) == (VAULT_MAP, PLAYER_ID)
    with pytest.raises(ValueError, match="already carries"):
        _ = turn(Move(entity_id=VAULT_MAP))
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
        _ = turn(Move(entity_id=VAULT_MAP))
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
    _ = turn(Move(to_id=CLOISTER))

    change = TraitChange(mode="add", entity_id=RAT, trait_id="hurt")
    kinds = turn.kinds(change)

    assert kinds == ["entity_discovered", "trait_added"]


def test_a_repeating_hook_fires_on_every_tick_of_its_clock() -> None:
    engine, state = initialized()
    draft = state.draft()
    draft.world.threads["ritual"] = Thread(
        id="ritual", title="The rite", clock=Counter(current=0, maximum=2)
    )
    draft.world.hooks = (
        Hook(
            id="rite-moves",
            once=False,
            match=HookMatch(kind="thread_advanced", data={"thread_id": "ritual"}),
            note="the rite moves on",
        ),
    )

    for filled in (1, 2):
        moved = apply_effect(draft, AdvanceThread(thread_id="ritual", tick=1))
        assert moved[0].data["clock_current"] == filled
        assert [fact.kind for fact in fire_hooks(draft, moved, engine.apply_effect)] == [
            "hook_fired"
        ]

    assert draft.world.fired_hooks == ("rite-moves",)
    assert draft.world.threads["ritual"].clock == Counter(current=2, maximum=2)


def test_a_tick_on_a_thread_without_a_clock_is_refused() -> None:
    turn = Applied()
    with pytest.raises(ValueError, match="no clock to tick"):
        _ = turn(AdvanceThread(thread_id="vault-seal", tick=1))


def test_a_hook_that_fills_a_clock_fires_the_filled_clock_hook_in_the_same_pass() -> None:
    engine, state = initialized()
    draft = state.draft()
    draft.world.threads["trial"] = Thread(
        id="trial", title="The trial", clock=Counter(current=0, maximum=2)
    )
    draft.world.hooks = (
        Hook(
            id="ticker",
            once=False,
            match=HookMatch(kind="entity_discovered"),
            effects=({"name": "advance-thread", "args": {"thread_id": "trial", "tick": 1}},),
        ),
        Hook(
            id="finale",
            match=HookMatch(kind="thread_advanced", data={"clock_filled": True}),
        ),
    )

    first = apply_effect(draft, Reveal(entity_id=VAULT_MAP))
    assert [fact.kind for fact in fire_hooks(draft, first, engine.apply_effect)] == [
        "hook_fired",
        "thread_advanced",
    ]

    second = apply_effect(draft, Reveal(entity_id=VAULT))
    assert [fact.kind for fact in fire_hooks(draft, second, engine.apply_effect)] == [
        "hook_fired",
        "thread_advanced",
        "hook_fired",
    ]


def test_a_hook_effect_the_vocabulary_does_not_take_lands_as_hook_failed() -> None:
    engine, state = initialized()
    draft = state.draft()
    draft.world.hooks = (
        Hook(
            id="broken",
            match=HookMatch(kind="entity_discovered"),
            effects=({"name": "no-such-call", "args": {}},),
        ),
    )

    seen = apply_effect(draft, Reveal(entity_id=VAULT_MAP))
    fired = fire_hooks(draft, seen, engine.apply_effect)

    assert [fact.kind for fact in fired] == ["hook_fired", "hook_failed"]


def test_hooks_that_feed_each_other_stop_at_the_round_cap() -> None:
    engine, state = initialized()
    draft = state.draft()
    draft.world.hooks = (Hook(id="self-feeder", once=False, match=HookMatch(kind="hook_fired")),)
    seed = Fact(source=CORE, kind="hook_fired", trace="seed")

    fired = fire_hooks(draft, [seed], engine.apply_effect)

    assert fired[-1].kind == "hooks_capped"
    assert sum(1 for fact in fired if fact.kind == "hook_fired") == MAX_HOOK_ROUNDS
