from support.table import (
    change,
    refused,
)
from support.tunnelgoons import (
    CELLAR,
    ENGINE,
    GATE,
    HALL,
    LANTERN,
    START,
    VAULT,
    WARDEN,
    YARD,
    keep,
    small_world,
)

from aidm.core.facts import Fact, cards
from aidm.engines.base import PLAYER_ID
from aidm.engines.rooms.tools import MOVED_CARD, MOVES_OFFSCREEN
from aidm.engines.rooms.world import MapProposal
from aidm.engines.tunnelgoons.engine import TunnelGoonsEngine
from aidm.engines.tunnelgoons.world import Goon, TunnelGoonsGame


def test_a_member_joins_and_leaves_the_party() -> None:
    draft = keep().draft()

    _ = change(ENGINE, draft, "join_party", target_id=WARDEN)

    assert WARDEN in draft.world.party

    _ = change(ENGINE, draft, "leave_party", target_id=WARDEN)

    assert draft.world.party == []


def test_killing_the_player_leaves_them_dead_and_a_second_kill_is_refused() -> None:
    draft = small_world().draft()

    facts = change(ENGINE, draft, "kill", target_id=PLAYER_ID)

    assert not draft.world.player.alive
    death = [fact for fact in facts if fact.card.startswith("You are dead")]
    assert len(death) == 1
    assert death[0].told
    assert "pack dropped: Rope, Torch" in death[0].card

    message = refused(ENGINE, draft, "kill", target_id=PLAYER_ID)

    assert "already dead" in message


def test_frontier_skips_places_behind_a_locked_way() -> None:
    world = small_world().world
    world.visits.append(HALL)
    for way in world.ways[START]:
        way.locked = way.to == VAULT

    assert world.frontier() == 0


def _walked(begun_room: TunnelGoonsGame) -> TunnelGoonsGame:
    """At CELLAR, having walked GATE and YARD: every power has something legal."""
    begun_room.world.move(YARD, ())
    begun_room.world.move(CELLAR, ())
    return begun_room.draft()


def _all_three(engine: TunnelGoonsEngine, draft: TunnelGoonsGame) -> list[Fact]:
    """One armed call spending every power: the warden walks, the lantern moves, a way shuts."""
    draft.world.meanwhile_due = True
    return change(
        engine,
        draft,
        "meanwhile",
        dweller_id=WARDEN,
        dweller_to_id=YARD,
        item_id=LANTERN,
        item_to_id=GATE,
        shut_from_id=GATE,
        shut_to_id=YARD,
    )


def test_meanwhile_moves_all_three_things_in_one_call() -> None:
    draft = _walked(keep())

    _ = _all_three(ENGINE, draft)

    world = draft.world
    assert world.npcs[WARDEN].place == YARD
    assert world.items[LANTERN].on == GATE
    way = world.way(GATE, YARD)
    assert way is not None
    assert way.locked
    assert not world.meanwhile_due


def test_meanwhile_never_reaches_the_narrator() -> None:
    draft = _walked(keep())

    facts = _all_three(ENGINE, draft)

    told = [fact for fact in facts if fact.told]
    assert len(told) == 1
    only = told[0]
    assert only.card == MOVED_CARD
    assert only.trace == MOVES_OFFSCREEN
    for name in ("Warden", "Lantern", "Gate", "Yard"):
        assert name not in only.trace
        assert name not in only.card
    assert cards(facts) == (only,)


def test_the_armed_flag_is_spent_only_on_a_counted_tick() -> None:
    draft = _walked(keep())
    draft.world.meanwhile_due = True

    ENGINE.tick(draft, counted=True)

    assert not draft.world.meanwhile_due

    draft.world.meanwhile_due = True

    ENGINE.tick(draft, counted=False)

    assert draft.world.meanwhile_due


def test_the_arc_reaches_the_master_and_the_worldsmith_and_nobody_else() -> None:
    begun_room = keep()
    arc = "The Warden answers to the Gremlin Queen."
    begun_room.world.arc = arc

    written = ENGINE.render_commission(
        begun_room, intent="More map.", guidance="", answer_model=MapProposal[Goon]
    )

    assert arc in str(ENGINE.master_sections(begun_room))
    assert arc in written
    assert arc not in str(ENGINE.narrator_view(begun_room).model_dump())
    assert arc not in str(ENGINE.player_view(begun_room).model_dump())
