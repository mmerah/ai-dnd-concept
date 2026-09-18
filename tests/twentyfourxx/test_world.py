import pytest
from support.twentyfourxx import KESTREL, hired, small_world

from aidm.core.entities import Refusal
from aidm.core.facts import DiceEvent
from aidm.engines.twentyfourxx.engine import items_from_kits
from aidm.engines.twentyfourxx.world import (
    DEFAULT_DIE,
    SHIP_FUNCTIONS,
    Crewmate,
    CrewSheet,
    Gear,
    Kit,
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


def test_raised_refuses_past_d12() -> None:
    with pytest.raises(Refusal):
        raised(12)


def test_sheet_die_returns_skill_or_default(world: TwentyfourxxWorld) -> None:
    sheet = world.player.require_sheet()
    assert sheet.die("Stealth") == 10
    assert sheet.die("Piloting") == DEFAULT_DIE


def test_a_members_line_spells_item_notes() -> None:
    crewmate = Crewmate(
        id=KESTREL,
        name="Kestrel",
        brief="A dockhand",
        known=True,
        sheet=CrewSheet(specialty="Muscle", items={"vest": Gear(name="Vest", bulky=True)}),
    )
    assert crewmate.line().endswith("  Vest[vest] (bulky)")


def test_rows_drops_empties_and_shows_credits() -> None:
    sheet = CrewSheet(specialty="Sneak", origin="Human", skills={"Stealth": 12})
    rows = dict(sheet.rows())
    assert rows["Skills"] == "Stealth d12"
    assert rows["Credits"] == "₡2"
    assert "Traits" not in rows
    assert "Hindrances" not in rows


def test_dice_refuses_on_an_unsheeted_member(world: TwentyfourxxWorld) -> None:
    with pytest.raises(Refusal, match="carries no dice"):
        world.cast[KESTREL].require_sheet()


def test_starting_items_slug_duplicate_kit_names_in_order() -> None:
    items = items_from_kits((Kit(name="Comm"), Kit(name="Comm")))
    assert list(items.keys()) == ["comm", "comm-2"]
    assert [item.name for item in items.values()] == ["Comm", "Comm"]


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


def test_take_lead_refused_while_the_player_lives(draft: TwentyfourxxGame) -> None:
    world = hired(draft, KESTREL, skills={"Shooting": 8}).world
    with pytest.raises(Refusal, match="lives and leads"):
        world.take_lead(KESTREL)


def test_require_gear_finds_a_ship_function_and_refuses_a_stranger() -> None:
    world = small_world().world
    item = world.require_gear(world.player, "hull-armor")
    assert item.name == "Hull armor"
    with pytest.raises(Refusal, match="not among"):
        world.require_gear(world.player, "nonexistent")


def test_item_detail_shows_upgraded() -> None:
    assert Gear(name="Comms", upgraded=True).notes() == "upgraded"


def test_every_crew_starts_with_the_seven_ship_functions(world: TwentyfourxxWorld) -> None:
    ship = world.ship
    assert [item.name for item in ship.values()] == list(SHIP_FUNCTIONS)
    assert list(ship)[4] == "hull-armor"


def test_hinder_twice_writes_only_one_fact(world: TwentyfourxxWorld) -> None:
    player = world.player
    facts = player.hinder("Winded")
    assert [fact.card for fact in facts] == ["Hindered: Winded"]
    assert player.require_sheet().hindrances == ["Winded"]
    assert player.hinder("Winded") == []


def test_raise_skill_sets_the_die_and_reports_it(world: TwentyfourxxWorld) -> None:
    player = world.player
    facts = player.raise_skill("Stealth")
    assert player.require_sheet().skills["Stealth"] == 12
    assert [fact.card for fact in facts] == ["Job done: Stealth d12"]


def test_raise_skill_at_d12_refuses_with_the_actors_name(world: TwentyfourxxWorld) -> None:
    player = world.player
    player.require_sheet().skills["Stealth"] = 12
    with pytest.raises(Refusal, match="Rook's Stealth is already at d12"):
        player.raise_skill("Stealth")


def test_earn_adds_credits_and_carries_the_event(world: TwentyfourxxWorld) -> None:
    player = world.player
    before = player.require_sheet().credits
    event = DiceEvent(label="d6", faces=(6,), rolled=(4,))
    facts = player.earn(4, event)
    assert player.require_sheet().credits == before + 4
    assert facts[0].dice == (event,)
    assert facts[0].card == f"+₡4 → ₡{before + 4}"


def test_take_job_refuses_when_one_is_already_open(world: TwentyfourxxWorld) -> None:
    world.job = "smuggle the crates"
    with pytest.raises(Refusal, match="a job is open"):
        world.take_job("a new job")


def test_take_job_sets_the_job_and_close_job_clears_it(world: TwentyfourxxWorld) -> None:
    facts = world.take_job("smuggle the crates")
    assert world.job == "smuggle the crates"
    assert facts[0].card == "Job taken\nsmuggle the crates"
    world.close_job()
    assert world.job == ""
