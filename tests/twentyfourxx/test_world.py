import pytest
from twentyfourxx_test_support import KESTREL, SABLE, small_world

from aidm.core.entities import EngineId, EntityId
from aidm.engines.core import PLAYER_ID
from aidm.engines.twentyfourxx.world import (
    DEFAULT_DIE,
    Item,
    Kit,
    Operator,
    TwentyfourxxCharacter,
    TwentyfourxxCharacterFile,
    TwentyfourxxWorld,
    player_operator,
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
    with pytest.raises(ValueError):
        raised(12)


def test_operator_die_returns_sheet_skill_or_default() -> None:
    operator = small_world().payload.world.player
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


def test_player_must_be_filed_as_player_id() -> None:
    world = small_world().payload.world
    bad_player = world.player.model_copy(update={"id": EntityId("not-player")})
    with pytest.raises(ValueError):
        TwentyfourxxWorld(cast=world.cast, player=bad_player, runs=world.runs)


def test_player_is_never_listed_in_the_scene() -> None:
    world = small_world().payload.world
    bad_run = world.run.model_copy(update={"present": [*world.run.present, PLAYER_ID]})
    with pytest.raises(ValueError):
        TwentyfourxxWorld(cast=world.cast, player=world.player, runs=[bad_run])


def test_check_filing_rejects_mis_filed_cast() -> None:
    world = small_world().payload.world
    with pytest.raises(ValueError):
        TwentyfourxxWorld(
            cast={EntityId("wrong-key"): world.cast[KESTREL]},
            player=world.player,
            runs=world.runs,
        )


def test_hidden_but_known_is_refused() -> None:
    world = small_world().payload.world
    cast = {**world.cast, SABLE: world.cast[SABLE].model_copy(update={"known": True})}
    with pytest.raises(ValueError):
        TwentyfourxxWorld(cast=cast, player=world.player, runs=world.runs)


def test_require_alive_here_refuses_dead_cast_member() -> None:
    world = small_world().payload.world
    world.cast[KESTREL].alive = False
    with pytest.raises(ValueError):
        world.require_alive_here(KESTREL)


def test_player_operator_slugs_duplicate_kit_names_in_order() -> None:
    character = TwentyfourxxCharacterFile(
        id="rook",
        engine=EngineId("twentyfourxx"),
        name="Rook",
        brief="A quiet operator",
        payload=TwentyfourxxCharacter(
            specialty="Sneak",
            origin="Human",
            skills={"Stealth": 10},
            items=(Kit(name="Comm"), Kit(name="Comm")),
        ),
    )
    operator = player_operator(character)
    assert list(operator.items.keys()) == [EntityId("comm"), EntityId("comm-2")]
    assert [item.name for item in operator.items.values()] == ["Comm", "Comm"]
