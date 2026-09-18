import pytest
from support.table import change
from support.twentyfourxx import ENGINE, KESTREL, hired, small_world

from aidm.core.entities import Refusal
from aidm.engines.twentyfourxx.world import (
    Gear,
    TwentyfourxxGame,
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


def test_take_lead_swaps_player_and_cast_entry_and_keeps_ids(draft: TwentyfourxxGame) -> None:
    world = hired(draft, KESTREL, skills={"Shooting": 8}).world
    dead_id = world.player.id
    world.player.alive = False
    facts = world.take_lead(KESTREL)

    assert world.player.id == KESTREL
    assert world.player.sheet is not None
    assert KESTREL not in world.cast
    assert KESTREL not in world.party
    assert world.cast[dead_id].id == dead_id
    assert not world.cast[dead_id].alive
    assert dead_id in world.scene.here
    assert any(fact.card == "Kestrel leads now" for fact in facts)
    TwentyfourxxWorld.model_validate_json(world.model_dump_json())


def test_the_new_lead_gets_the_cards_and_the_line_of_a_player(draft: TwentyfourxxGame) -> None:
    led = hired(draft, KESTREL, skills={"Shooting": 8}).draft()
    world = led.world
    world.player.alive = False
    _ = world.take_lead(KESTREL)
    world.player.require_sheet().credits = 2
    world.player.require_sheet().items["vest"] = Gear(name="Vest")

    facts = change(ENGINE, led, "spend", amount=1, why="a bribe")

    assert [fact.card for fact in facts] == ["₡1 spent — a bribe"]
    assert world.cast_lines().partition("\n- ")[0].count("Vest") == 1


def test_require_gear_finds_a_ship_function_and_refuses_a_stranger() -> None:
    world = small_world().world
    item = world.require_gear(world.player, "hull-armor")
    assert item.name == "Hull armor"
    with pytest.raises(Refusal, match="not among"):
        world.require_gear(world.player, "nonexistent")


def test_hinder_twice_writes_only_one_fact(world: TwentyfourxxWorld) -> None:
    player = world.player
    facts = player.hinder("Winded", leads=True)
    assert [fact.card for fact in facts] == ["Hindered: Winded"]
    assert player.require_sheet().hindrances == ["Winded"]
    assert player.hinder("Winded", leads=True) == []
