from random import Random

import pytest
from support.sixth import CELLAR, GATE, LANTERN, WARDEN, WELL, YARD, SixthEngine, SixthGame
from support.table import (
    ENGINES_BUILT,
    LIBRARY,
    SCENARIO_MODELS,
    TUNNELGOONS,
    change,
    narrowed,
    refused,
    scenario_for,
    updated,
)

from aidm.core.entities import Refusal
from aidm.core.facts import Fact, cards
from aidm.core.model import PackSelection
from aidm.engines.base import PLAYER_ID
from aidm.engines.rooms.engine import ELSEWHERE
from aidm.engines.rooms.tools import Move
from aidm.engines.rooms.world import MOVED_CARD, MOVES_OFFSCREEN, NOTHING_OFFSCREEN, Prop, Way
from aidm.engines.tunnelgoons.world import TunnelGoonsGame


def test_a_sixth_room_engine_begins_a_playable_game(
    room_engine: SixthEngine, begun_room: SixthGame
) -> None:
    assert room_engine.master_sections(begun_room)[0] == ("CURRENT PLACE", "Gate[gate]\nGate")
    ways_out = next(
        panel for panel in room_engine.player_view(begun_room).panels if panel.title == "Ways out"
    )
    assert [row.label for row in ways_out.rows] == ["Yard"]
    room_engine.move(begun_room, Move(to_id=YARD), Random(0))
    assert begun_room.payload.visits == [GATE, YARD]


def test_the_familys_tools_are_offered_in_order(
    room_engine: SixthEngine, begun_room: SixthGame
) -> None:
    assert list(room_engine.tools) == [
        "reveal",
        "kill",
        "join_party",
        "leave_party",
        "move_item",
        "unlock_way",
        "move",
        "meanwhile",
    ]
    draft = begun_room.draft()

    _ = change(room_engine, draft, "join_party", entity_id=WARDEN)

    assert WARDEN in draft.payload.party

    _ = change(room_engine, draft, "leave_party", entity_id=WARDEN)

    assert draft.payload.party == []


def test_leave_party_on_a_non_member_is_refused(
    room_engine: SixthEngine, begun_room: SixthGame
) -> None:
    draft = begun_room.draft()

    message = refused(room_engine, draft, "leave_party", entity_id=WARDEN)

    assert "does not travel with the player" in message


def test_require_member_here_refuses_an_unknown_co_located_npc(begun_room: SixthGame) -> None:
    world = begun_room.payload
    world.npcs[WARDEN].known = False

    with pytest.raises(Refusal, match="not here with the player"):
        world.require_member_here(WARDEN)


def test_a_room_world_refuses_an_npc_filed_under_the_player_id(begun_room: SixthGame) -> None:
    world = begun_room.payload
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


def test_an_item_on_the_player_must_be_known(begun_room: SixthGame) -> None:
    world = begun_room.payload
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


def test_a_party_member_is_absent_from_place_lines_while_their_items_stay(
    room_engine: SixthEngine, begun_room: SixthGame
) -> None:
    world = begun_room.payload
    key = "warden-key"
    world.items[key] = Prop(id=key, name="Key", brief="A rusty key", known=True, on=WARDEN)
    world.party.append(WARDEN)

    lines = world.place_lines(known=True)

    assert "Warden[warden]" not in lines
    assert "Key[warden-key]" in lines

    panels = room_engine.player_view(begun_room).panels
    party_rows = next(panel for panel in panels if panel.title == "Party").rows
    here_rows = next(panel for panel in panels if panel.title == "Also here").rows

    assert any(row.icon_id == WARDEN for row in party_rows)
    assert all(row.icon_id != WARDEN for row in here_rows)


def test_killing_the_player_leaves_them_dead_and_a_second_kill_is_refused(
    room_engine: SixthEngine, begun_room: SixthGame
) -> None:
    draft = begun_room.draft()

    facts = change(room_engine, draft, "kill", entity_id=PLAYER_ID)

    assert not draft.payload.player.alive
    assert any(fact.card == "You are dead" for fact in facts)

    message = refused(room_engine, draft, "kill", entity_id=PLAYER_ID)

    assert "already dead" in message


def test_move_does_not_clear_an_authored_lock_on_the_way_back(
    room_engine: SixthEngine, begun_room: SixthGame
) -> None:
    world = begun_room.payload
    world.ways[YARD].append(Way(to=GATE, locked=True))

    room_engine.move(begun_room, Move(to_id=YARD), Random(0))

    back = world.way(YARD, GATE)
    assert back is not None
    assert back.locked


def test_a_room_game_given_a_table_set_is_refused(
    room_engine: SixthEngine, begun_room: SixthGame
) -> None:
    stranded = updated(begun_room, packs=PackSelection(ids=("srd",)))

    with pytest.raises(Refusal, match="plays no table set"):
        room_engine.validate(stranded)


def test_beginning_the_game_does_not_mutate_the_authored_scenario() -> None:
    engine = ENGINES_BUILT[TUNNELGOONS]
    scenario_id = scenario_for(TUNNELGOONS)
    scenario = LIBRARY.read_scenario(scenario_id, SCENARIO_MODELS)
    before = scenario.payload.model_dump()
    character = LIBRARY.read_character("kael", engine.id, engine.character)
    draft = engine.begin(scenario_id, scenario, character)
    world = narrowed(draft, TunnelGoonsGame).payload

    next(iter(world.npcs.values())).name = "Someone else"

    assert scenario.payload.model_dump() == before


def _walked(room_engine: SixthEngine, begun_room: SixthGame) -> SixthGame:
    """At CELLAR, having walked GATE and YARD: every power has something legal."""
    room_engine.move(begun_room, Move(to_id=YARD), Random(0))
    room_engine.move(begun_room, Move(to_id=CELLAR), Random(0))
    return begun_room.draft()


def _all_three(engine: SixthEngine, draft: SixthGame) -> list[Fact]:
    """One armed call spending every power: the warden walks, the lantern moves, a way shuts."""
    draft.payload.meanwhile_due = True
    return change(
        engine,
        draft,
        "meanwhile",
        dweller_id=WARDEN,
        dweller_to=YARD,
        item_id=LANTERN,
        item_to=GATE,
        shut_from=GATE,
        shut_to=YARD,
    )


def test_meanwhile_moves_all_three_things_in_one_call(
    room_engine: SixthEngine, begun_room: SixthGame
) -> None:
    draft = _walked(room_engine, begun_room)

    _ = _all_three(room_engine, draft)

    world = draft.payload
    assert world.npcs[WARDEN].place == YARD
    assert world.items[LANTERN].on == GATE
    way = world.way(GATE, YARD)
    assert way is not None
    assert way.locked
    assert not world.meanwhile_due


def test_meanwhile_never_reaches_the_narrator(
    room_engine: SixthEngine, begun_room: SixthGame
) -> None:
    draft = _walked(room_engine, begun_room)

    facts = _all_three(room_engine, draft)

    told = [fact for fact in facts if fact.told]
    assert len(told) == 1
    only = told[0]
    assert only.card == MOVED_CARD
    assert only.trace == MOVES_OFFSCREEN
    for name in ("Warden", "Lantern", "Gate", "Yard"):
        assert name not in only.trace
        assert name not in only.card
    assert cards(facts) == (only,)


def test_meanwhile_refusals(room_engine: SixthEngine, begun_room: SixthGame) -> None:
    draft = _walked(room_engine, begun_room)
    world = draft.payload

    assert NOTHING_OFFSCREEN in refused(
        room_engine, draft, "meanwhile", dweller_id=WARDEN, dweller_to=YARD
    )

    world.meanwhile_due = True
    assert "give a dweller, an item or a way to shut" in refused(room_engine, draft, "meanwhile")
    assert "both ends or neither" in refused(room_engine, draft, "meanwhile", dweller_id=WARDEN)
    assert "unknown id" in refused(
        room_engine, draft, "meanwhile", dweller_id="nobody", dweller_to=YARD
    )
    assert "unknown id" in refused(
        room_engine, draft, "meanwhile", dweller_id=GATE, dweller_to=YARD
    )

    world.npcs[WARDEN].place = CELLAR
    assert "stands with the player" in refused(
        room_engine, draft, "meanwhile", dweller_id=WARDEN, dweller_to=YARD
    )
    world.npcs[WARDEN].place = GATE

    world.items[LANTERN].on = CELLAR
    assert "is here with the player" in refused(
        room_engine, draft, "meanwhile", item_id=LANTERN, item_to=GATE
    )

    world.npcs[WARDEN].place = CELLAR
    world.items[LANTERN].on = WARDEN
    assert "is here with the player" in refused(
        room_engine, draft, "meanwhile", item_id=LANTERN, item_to=GATE
    )
    world.npcs[WARDEN].place = GATE
    world.items[LANTERN].on = YARD

    assert "is already there" in refused(
        room_engine, draft, "meanwhile", item_id=LANTERN, item_to=YARD
    )

    world.npcs[WARDEN].alive = False
    assert "takes no further part" in refused(
        room_engine, draft, "meanwhile", dweller_id=WARDEN, dweller_to=YARD
    )
    world.npcs[WARDEN].alive = True

    world.npcs[WARDEN].place = YARD
    assert "no unlocked way leads" in refused(
        room_engine, draft, "meanwhile", dweller_id=WARDEN, dweller_to=GATE
    )
    world.npcs[WARDEN].place = GATE

    message = refused(room_engine, draft, "meanwhile", dweller_id=WARDEN, dweller_to=WELL)
    assert "Gate" in message and "Yard" in message

    message = refused(room_engine, draft, "meanwhile", dweller_id=WARDEN, dweller_to=CELLAR)
    assert "Gate" in message and "Yard" in message

    way = world.way(GATE, YARD)
    assert way is not None
    way.known = False
    assert "has not found" in refused(room_engine, draft, "meanwhile", shut_from=GATE, shut_to=YARD)
    way.known = True

    assert "cannot shut offscreen" in refused(
        room_engine, draft, "meanwhile", shut_from=YARD, shut_to=CELLAR
    )


def test_the_armed_flag_is_spent_only_on_a_counted_tick(
    room_engine: SixthEngine, begun_room: SixthGame
) -> None:
    draft = _walked(room_engine, begun_room)
    draft.payload.meanwhile_due = True

    room_engine.tick(draft, counted=True)

    assert not draft.payload.meanwhile_due

    draft.payload.meanwhile_due = True

    room_engine.tick(draft, counted=False)

    assert draft.payload.meanwhile_due


def test_the_clock_does_not_arm_with_nothing_to_move_and_keeps_the_count(
    room_engine: SixthEngine, begun_room: SixthGame
) -> None:
    draft = begun_room.draft()
    world = draft.payload
    assert world.elsewhere() == []
    assert not world.can_move_offscreen()

    world.turns_played = 3
    room_engine.tick(draft, counted=True)

    assert world.turns_played == 3
    assert not world.meanwhile_due

    room_engine.move(draft, Move(to_id=YARD), Random(0))
    room_engine.move(draft, Move(to_id=CELLAR), Random(0))
    room_engine.tick(draft, counted=True)

    assert world.turns_played == 4


def test_can_move_offscreen_is_false_when_the_only_item_sits_in_a_here_dwellers_hands(
    room_engine: SixthEngine, begun_room: SixthGame
) -> None:
    draft = _walked(room_engine, begun_room)
    world = draft.payload
    world.npcs[WARDEN].place = CELLAR
    world.items[LANTERN].on = WARDEN
    way = world.way(GATE, YARD)
    assert way is not None
    way.known = False  # neutralise the shut power: this test pins the holder set alone

    assert not world.can_move_offscreen()


def test_can_move_offscreen_counts_the_shut_power_and_ignores_a_never_visited_place(
    room_engine: SixthEngine, begun_room: SixthGame
) -> None:
    draft = _walked(room_engine, begun_room)
    world = draft.payload
    world.items[LANTERN].on = WELL
    world.npcs[WARDEN].place = WELL
    way = world.way(GATE, YARD)
    assert way is not None

    way.known = False
    assert not world.can_move_offscreen()

    way.known = True
    assert world.can_move_offscreen()


def test_the_elsewhere_section_shows_only_when_the_clock_is_armed(
    room_engine: SixthEngine, begun_room: SixthGame
) -> None:
    draft = _walked(room_engine, begun_room)
    assert ELSEWHERE not in dict(room_engine.master_sections(draft))

    draft.payload.meanwhile_due = True

    section = dict(room_engine.master_sections(draft))[ELSEWHERE]

    assert "Gate" in section
    assert "Yard" in section
    assert "Warden" in section
    assert "Lantern" in section
    assert "Cellar" in section
    assert "Well" not in section
