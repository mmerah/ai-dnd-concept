import pytest
from support.twentyfourxx import KESTREL, hired, small_world

from aidm.core.entities import EntityId, Refusal
from aidm.engines.base import PLAYER_ID
from aidm.engines.twentyfourxx.engine import starting_items
from aidm.engines.twentyfourxx.world import (
    DEFAULT_DIE,
    Crewmate,
    Item,
    Kit,
    Sheet,
    TwentyfourxxWorld,
    raised,
)


def test_item_broken_at_and_below_breaks() -> None:
    item = Item(name="Vest", breaks=2)
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
    sheet = small_world().payload.player.dice()
    assert sheet.die("Stealth") == 10
    assert sheet.die("Piloting") == DEFAULT_DIE


def test_rows_drops_empties_and_shows_credits() -> None:
    sheet = Sheet(specialty="Sneak", origin="Human", skills={"Stealth": 12})
    rows = dict(sheet.rows())
    assert rows["Skills"] == "Stealth d12"
    assert rows["Credits"] == "₡2"
    assert "Traits" not in rows
    assert "Hindrances" not in rows


def test_dice_refuses_on_an_unsheeted_member() -> None:
    world = small_world().payload
    with pytest.raises(Refusal, match="carries no dice"):
        world.cast[KESTREL].dice()


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
            cast={EntityId("wrong-key"): world.cast[KESTREL]},
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
    with pytest.raises(Refusal, match="not the player or a hired crew member"):
        world.require_actor(KESTREL)


def test_starting_items_slug_duplicate_kit_names_in_order() -> None:
    items = starting_items((Kit(name="Comm"), Kit(name="Comm")))
    assert list(items.keys()) == [EntityId("comm"), EntityId("comm-2")]
    assert [item.name for item in items.values()] == ["Comm", "Comm"]
