import pytest
from support.table import (
    ENGINES_BUILT,
    LIBRARY,
    NO_PACKS,
    SCENARIO_MODELS,
    TUNNELGOONS,
    change,
    narrowed,
    refused,
    scenario_for,
    updated,
)
from support.tunnelgoons import CELLAR, ENGINE, GATE, LANTERN, WARDEN, WELL, YARD, keep

from aidm.core.entities import Refusal
from aidm.core.facts import Fact, cards
from aidm.engines.base import PLAYER_ID
from aidm.engines.packs import SRD_PACK, PackSet
from aidm.engines.rooms.tools import ELSEWHERE, MOVED_CARD, MOVES_OFFSCREEN, NOTHING_OFFSCREEN
from aidm.engines.rooms.world import MapProposal, Prop, Way
from aidm.engines.tunnelgoons.engine import TunnelGoonsEngine
from aidm.engines.tunnelgoons.pack import TunnelGoonsPack
from aidm.engines.tunnelgoons.world import Npc, TunnelGoonsGame


def test_a_room_game_shows_its_place_and_its_ways_out() -> None:
    begun_room = keep()
    assert ENGINE.master_sections(begun_room)[0] == ("CURRENT PLACE", "Gate[gate]\nGate")
    ways_out = next(
        panel for panel in ENGINE.player_view(begun_room).panels if panel.title == "Ways out"
    )
    assert [row.name for row in ways_out.rows] == ["Yard"]
    begun_room.world.move(YARD, ())
    assert begun_room.world.visits == [GATE, YARD]


def test_a_member_joins_and_leaves_the_party() -> None:
    draft = keep().draft()

    _ = change(ENGINE, draft, "join_party", target_id=WARDEN)

    assert WARDEN in draft.world.party

    _ = change(ENGINE, draft, "leave_party", target_id=WARDEN)

    assert draft.world.party == []


def test_leave_party_on_a_non_member_is_refused() -> None:
    draft = keep().draft()

    message = refused(ENGINE, draft, "leave_party", target_id=WARDEN)

    assert "does not travel with the player" in message


def test_require_member_here_refuses_an_unknown_co_located_npc() -> None:
    world = keep().world
    world.npcs[WARDEN].known = False

    with pytest.raises(Refusal, match="not here with the player"):
        world.require_member_here(WARDEN)


def test_a_room_world_refuses_an_npc_filed_under_the_player_id() -> None:
    world = keep().world
    decoy = world.npcs[WARDEN].model_copy(update={"id": PLAYER_ID})

    with pytest.raises(ValueError, match="duplicate"):
        type(world)(
            places=world.places,
            ways=world.ways,
            npcs={**world.npcs, PLAYER_ID: decoy},
            items=world.items,
            visits=world.visits,
            player=world.player,
        )


def test_an_item_on_the_player_must_be_known() -> None:
    world = keep().world
    hidden = world.items[LANTERN].model_copy(update={"on": PLAYER_ID, "known": False})

    with pytest.raises(ValueError, match="unknown to them"):
        type(world)(
            places=world.places,
            ways=world.ways,
            npcs=world.npcs,
            items={**world.items, LANTERN: hidden},
            visits=world.visits,
            player=world.player,
        )


def test_a_party_member_is_absent_from_place_lines_while_their_items_stay() -> None:
    begun_room = keep()
    world = begun_room.world
    key = "warden-key"
    world.items[key] = Prop(id=key, name="Key", brief="A rusty key", known=True, on=WARDEN)
    world.party.append(WARDEN)

    lines = world.place_lines(known=True)

    assert "Warden[warden]" not in lines
    assert "Key[warden-key]" in lines

    panels = ENGINE.player_view(begun_room).panels
    party_rows = next(panel for panel in panels if panel.title == "Party").rows
    here_rows = next(panel for panel in panels if panel.title == "Also here").rows

    assert any(row.icon_id == WARDEN for row in party_rows)
    assert all(row.icon_id != WARDEN for row in here_rows)


def test_killing_the_player_leaves_them_dead_and_a_second_kill_is_refused() -> None:
    draft = keep().draft()

    facts = change(ENGINE, draft, "kill", target_id=PLAYER_ID)

    assert not draft.world.player.alive
    assert any(fact.card == "You are dead" for fact in facts)

    message = refused(ENGINE, draft, "kill", target_id=PLAYER_ID)

    assert "already dead" in message


def test_move_does_not_clear_an_authored_lock_on_the_way_back() -> None:
    world = keep().world
    world.ways[YARD].append(Way(to=GATE, locked=True))

    world.move(YARD, ())

    back = world.way(YARD, GATE)
    assert back is not None
    assert back.locked


def test_a_room_game_validates_the_pack_it_plays() -> None:
    engine = TunnelGoonsEngine(NO_PACKS)
    engine.packs = PackSet(
        engine.id,
        {
            SRD_PACK: engine.packs.srd(),
            "mine": TunnelGoonsPack(name="Mine", source="", license=""),
        },
        {},
    )
    begun_room = keep()

    played = updated(begun_room, pack_id="mine")
    assert engine.restore(played.model_dump_json()).pack_id == "mine"

    with pytest.raises(Refusal, match="is not installed"):
        _ = engine.restore(updated(played, pack_id="gone").model_dump_json())


def test_beginning_the_game_does_not_mutate_the_authored_scenario() -> None:
    engine = ENGINES_BUILT[TUNNELGOONS]
    scenario_id = scenario_for(TUNNELGOONS)
    scenario = LIBRARY.read_scenario(scenario_id, SCENARIO_MODELS)
    before = scenario.opening.model_dump()
    character = LIBRARY.read_character("kael", engine.id, engine.character)
    draft = engine.begin(scenario_id, scenario, character)
    world = narrowed(draft, TunnelGoonsGame).world

    next(iter(world.npcs.values())).name = "Someone else"

    assert scenario.opening.model_dump() == before


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


def test_meanwhile_refusals() -> None:
    draft = _walked(keep())
    world = draft.world

    assert NOTHING_OFFSCREEN in refused(
        ENGINE, draft, "meanwhile", dweller_id=WARDEN, dweller_to_id=YARD
    )

    world.meanwhile_due = True
    assert "give a dweller, an item or a way to shut" in refused(ENGINE, draft, "meanwhile")
    assert "both ends or neither" in refused(ENGINE, draft, "meanwhile", dweller_id=WARDEN)
    assert "unknown id" in refused(
        ENGINE, draft, "meanwhile", dweller_id="nobody", dweller_to_id=YARD
    )
    assert "unknown id" in refused(ENGINE, draft, "meanwhile", dweller_id=GATE, dweller_to_id=YARD)

    world.npcs[WARDEN].place = CELLAR
    assert "stands with the player" in refused(
        ENGINE, draft, "meanwhile", dweller_id=WARDEN, dweller_to_id=YARD
    )
    world.npcs[WARDEN].place = GATE

    world.items[LANTERN].on = CELLAR
    assert "is here with the player" in refused(
        ENGINE, draft, "meanwhile", item_id=LANTERN, item_to_id=GATE
    )

    world.npcs[WARDEN].place = CELLAR
    world.items[LANTERN].on = WARDEN
    assert "is here with the player" in refused(
        ENGINE, draft, "meanwhile", item_id=LANTERN, item_to_id=GATE
    )
    world.npcs[WARDEN].place = GATE
    world.items[LANTERN].on = YARD

    assert "is already there" in refused(
        ENGINE, draft, "meanwhile", item_id=LANTERN, item_to_id=YARD
    )

    world.npcs[WARDEN].alive = False
    assert "takes no further part" in refused(
        ENGINE, draft, "meanwhile", dweller_id=WARDEN, dweller_to_id=YARD
    )
    world.npcs[WARDEN].alive = True

    world.npcs[WARDEN].place = YARD
    assert "no unlocked way leads" in refused(
        ENGINE, draft, "meanwhile", dweller_id=WARDEN, dweller_to_id=GATE
    )
    world.npcs[WARDEN].place = GATE

    message = refused(ENGINE, draft, "meanwhile", dweller_id=WARDEN, dweller_to_id=WELL)
    assert "Gate" in message and "Yard" in message

    message = refused(ENGINE, draft, "meanwhile", dweller_id=WARDEN, dweller_to_id=CELLAR)
    assert "Gate" in message and "Yard" in message

    way = world.way(GATE, YARD)
    assert way is not None
    way.known = False
    assert "has not found" in refused(
        ENGINE, draft, "meanwhile", shut_from_id=GATE, shut_to_id=YARD
    )
    way.known = True

    assert "cannot shut offscreen" in refused(
        ENGINE, draft, "meanwhile", shut_from_id=YARD, shut_to_id=CELLAR
    )


def test_the_armed_flag_is_spent_only_on_a_counted_tick() -> None:
    draft = _walked(keep())
    draft.world.meanwhile_due = True

    ENGINE.tick(draft, counted=True)

    assert not draft.world.meanwhile_due

    draft.world.meanwhile_due = True

    ENGINE.tick(draft, counted=False)

    assert draft.world.meanwhile_due


def test_the_clock_does_not_arm_with_nothing_to_move_and_keeps_the_count() -> None:
    draft = keep().draft()
    world = draft.world
    assert world.elsewhere() == []
    assert not world.can_move_offscreen()

    world.turns_played = 1
    ENGINE.tick(draft, counted=True)

    assert world.turns_played == 1
    assert not world.meanwhile_due

    world.move(YARD, ())
    world.move(CELLAR, ())
    ENGINE.tick(draft, counted=True)

    assert world.turns_played == 2


def test_can_move_offscreen_is_false_when_the_only_item_sits_in_a_here_dwellers_hands() -> None:
    draft = _walked(keep())
    world = draft.world
    world.npcs[WARDEN].place = CELLAR
    world.items[LANTERN].on = WARDEN
    way = world.way(GATE, YARD)
    assert way is not None
    way.known = False  # neutralise the shut power: this test pins the holder set alone

    assert not world.can_move_offscreen()


def test_can_move_offscreen_counts_the_shut_power_and_ignores_a_never_visited_place() -> None:
    draft = _walked(keep())
    world = draft.world
    world.items[LANTERN].on = WELL
    world.npcs[WARDEN].place = WELL
    way = world.way(GATE, YARD)
    assert way is not None

    way.known = False
    assert not world.can_move_offscreen()

    way.known = True
    assert world.can_move_offscreen()


def test_the_elsewhere_section_shows_only_when_the_clock_is_armed() -> None:
    draft = _walked(keep())
    assert ELSEWHERE not in dict(ENGINE.master_sections(draft))

    draft.world.meanwhile_due = True

    section = dict(ENGINE.master_sections(draft))[ELSEWHERE]

    assert "Gate" in section
    assert "Yard" in section
    assert "Warden" in section
    assert "Lantern" in section
    assert "Cellar" in section
    assert "Well" not in section


def test_the_arc_reaches_the_master_and_the_worldsmith_and_nobody_else() -> None:
    begun_room = keep()
    arc = "The Warden answers to the Gremlin Queen."
    begun_room.world.arc = arc

    written = ENGINE.render_commission(
        begun_room, intent="More map.", guidance="", answer_model=MapProposal[Npc]
    )

    assert arc in str(ENGINE.master_sections(begun_room))
    assert arc in written
    assert arc not in str(ENGINE.narrator_view(begun_room).model_dump())
    assert arc not in str(ENGINE.player_view(begun_room).model_dump())
