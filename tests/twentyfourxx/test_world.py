import pytest
from support.twentyfourxx import KESTREL, hired, small_world

from aidm.core.entities import Refusal
from aidm.engines.base import PLAYER_ID
from aidm.engines.twentyfourxx.engine import items_from_kits
from aidm.engines.twentyfourxx.world import (
    DEFAULT_DIE,
    SHIP_FUNCTIONS,
    Crewmate,
    CrewSheet,
    Gear,
    Kit,
    TwentyfourxxWorld,
    raised,
)


def test_item_broken_at_and_below_breaks() -> None:
    item = Gear(name="Vest", breaks=2)
    assert not item.broken
    item.broken_times = 1
    assert not item.broken
    item.broken_times = 2
    assert item.broken


def test_raised_steps_up_the_ladder() -> None:
    assert raised(None) == 8
    assert raised(8) == 10
    assert raised(10) == 12


def test_raised_refuses_past_d12() -> None:
    with pytest.raises(Refusal):
        raised(12)


def test_sheet_die_returns_skill_or_default() -> None:
    sheet = small_world().payload.player.require_sheet()
    assert sheet.die("Stealth") == 10
    assert sheet.die("Piloting") == DEFAULT_DIE


def test_rows_drops_empties_and_shows_credits() -> None:
    sheet = CrewSheet(specialty="Sneak", origin="Human", skills={"Stealth": 12})
    rows = dict(sheet.rows())
    assert rows["Skills"] == "Stealth d12"
    assert rows["Credits"] == "₡2"
    assert "Traits" not in rows
    assert "Hindrances" not in rows


def test_dice_refuses_on_an_unsheeted_member() -> None:
    world = small_world().payload
    with pytest.raises(Refusal, match="carries no dice"):
        world.cast[KESTREL].require_sheet()


def test_a_player_with_no_sheet_is_refused() -> None:
    world = small_world().payload
    unsheeted = world.player.model_copy(update={"sheet": None})
    with pytest.raises(ValueError, match="the player carries no sheet"):
        TwentyfourxxWorld(cast=world.cast, player=unsheeted, runs=world.runs)


def test_a_cast_that_holds_the_player_is_refused() -> None:
    world = small_world().payload
    decoy = Crewmate(id=PLAYER_ID, name="Someone", brief="filed wrongly", known=True)
    with pytest.raises(ValueError, match="the player is in the cast"):
        TwentyfourxxWorld(
            cast={**world.cast, PLAYER_ID: decoy}, player=world.player, runs=world.runs
        )


def test_player_is_never_listed_in_the_scene() -> None:
    world = small_world().payload
    bad_run = world.run.model_copy(update={"here": [*world.run.here, PLAYER_ID]})
    with pytest.raises(ValueError):
        TwentyfourxxWorld(cast=world.cast, player=world.player, runs=[bad_run])


def test_check_filing_rejects_mis_filed_cast() -> None:
    world = small_world().payload
    with pytest.raises(ValueError):
        TwentyfourxxWorld(
            cast={"wrong-key": world.cast[KESTREL]},
            player=world.player,
            runs=world.runs,
        )


def test_require_here_alive_refuses_dead_cast_member() -> None:
    world = small_world().payload
    world.cast[KESTREL].alive = False
    with pytest.raises(Refusal):
        world.require_here(KESTREL, alive=True)


def test_require_actor_none_is_the_player() -> None:
    world = small_world().payload
    assert world.require_actor(None) is world.player
    assert world.require_actor(PLAYER_ID) is world.player


def test_require_actor_accepts_a_living_sheeted_party_member() -> None:
    world = hired(small_world(), KESTREL, skills={"Shooting": 8}).payload
    assert world.require_actor(KESTREL) is world.cast[KESTREL]


def test_require_actor_refuses_an_unsheeted_member() -> None:
    world = small_world().payload
    world.party = [KESTREL]
    with pytest.raises(Refusal, match="not the player or a hired party member"):
        world.require_actor(KESTREL)


def test_starting_items_slug_duplicate_kit_names_in_order() -> None:
    items = items_from_kits((Kit(name="Comm"), Kit(name="Comm")))
    assert list(items.keys()) == ["comm", "comm-2"]
    assert [item.name for item in items.values()] == ["Comm", "Comm"]


def test_take_lead_swaps_player_and_cast_entry_and_keeps_ids() -> None:
    world = hired(small_world(), KESTREL, skills={"Shooting": 8}).payload
    dead_id = world.player.id
    world.player.alive = False
    facts = world.take_lead(KESTREL)

    assert world.player.id == KESTREL
    assert world.player.sheet is not None
    assert KESTREL not in world.cast
    assert KESTREL not in world.party
    assert world.cast[dead_id].id == dead_id
    assert not world.cast[dead_id].alive
    assert dead_id in world.run.here
    assert any(fact.card == "Kestrel leads now" for fact in facts)
    TwentyfourxxWorld.model_validate(world.model_dump(mode="json"))


def test_take_lead_refused_while_the_player_lives() -> None:
    world = hired(small_world(), KESTREL, skills={"Shooting": 8}).payload
    with pytest.raises(Refusal, match="lives and leads"):
        world.take_lead(KESTREL)


def test_require_gear_finds_a_ship_function_and_refuses_a_stranger() -> None:
    world = small_world().payload
    item = world.require_gear(world.player, "hull-armor")
    assert item.name == "Hull armor"
    with pytest.raises(Refusal, match="not among"):
        world.require_gear(world.player, "nonexistent")


def test_item_detail_shows_upgraded() -> None:
    assert Gear(name="Comms", upgraded=True).notes() == "upgraded"


def test_every_crew_starts_with_the_seven_ship_functions() -> None:
    ship = small_world().payload.ship
    assert [item.name for item in ship.values()] == list(SHIP_FUNCTIONS)
    assert list(ship)[4] == "hull-armor"
