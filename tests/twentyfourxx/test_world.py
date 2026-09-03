import pytest
from support.table import ENGINES_BUILT, TWENTYFOURXX
from support.twentyfourxx import KESTREL, hub_world, small_world

from aidm.core.entities import EntityId, Refusal
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.twentyfourxx.engine import starting_items
from aidm.engines.twentyfourxx.world import (
    DEFAULT_DIE,
    Item,
    Kit,
    Operator,
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


def test_operator_die_returns_sheet_skill_or_default() -> None:
    operator = small_world().payload.player
    assert operator.die("Stealth") == 10
    assert operator.die("Piloting") == DEFAULT_DIE


def test_rows_drops_empties_and_shows_credits() -> None:
    operator = Operator(
        id=PLAYER_ID,
        name="Rook",
        brief="",
        specialty="Sneak",
        origin="Human",
        skills={"Stealth": 12},
    )
    rows = dict(operator.rows())
    assert rows["Skills"] == "Stealth d12"
    assert rows["Credits"] == "₡2"
    assert "Traits" not in rows
    assert "Hindrances" not in rows


def test_a_cast_that_holds_the_player_is_refused() -> None:
    world = small_world().payload
    decoy = Person(id=PLAYER_ID, name="Someone", brief="filed wrongly", known=True)
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


def test_require_alive_here_refuses_dead_cast_member() -> None:
    world = small_world().payload
    world.cast[KESTREL].alive = False
    with pytest.raises(Refusal):
        world.require_alive_here(KESTREL)


def test_way_open_is_true_at_an_unsettled_hub() -> None:
    game = hub_world()
    assert (
        ENGINES_BUILT[TWENTYFOURXX].ready(game) is False
    )  # away on a job, with the scene's question still open

    _ = game.payload.runs.pop()  # home again, where the way on is always open
    assert ENGINES_BUILT[TWENTYFOURXX].ready(game) is True


def test_starting_items_slug_duplicate_kit_names_in_order() -> None:
    items = starting_items((Kit(name="Comm"), Kit(name="Comm")))
    assert list(items.keys()) == [EntityId("comm"), EntityId("comm-2")]
    assert [item.name for item in items.values()] == ["Comm", "Comm"]
