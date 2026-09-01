import pytest
from pydantic import BaseModel

from aidm.core.entities import EntityId, Trait
from aidm.kits.entities import Entity, Thread
from aidm.kits.rooms.boundary import frontier
from aidm.kits.rooms.state import RoomVisit, RoomWorld, Way
from aidm.kits.rooms.verbs import Kill, MoveItem, apply_change, move
from aidm.kits.rooms.worldsmith import MapDraft, map_refusal, render_map


class Sheet(BaseModel):
    pass


def e(value: str) -> EntityId:
    return EntityId(value)


def _world() -> RoomWorld[Sheet]:
    places = {
        e(name): Entity[Sheet](
            id=e(name), kind="place", name=name, brief=name, known=name == "hall"
        )
        for name in ("hall", "crypt")
    }
    player = Entity[Sheet](
        id=e("player"),
        kind="actor",
        name="Player",
        brief="hero",
        known=True,
        carried_by=e("hall"),
    )
    companion = Entity[Sheet](
        id=e("mara"),
        kind="actor",
        name="Mara",
        brief="guide",
        known=True,
        carried_by=e("hall"),
    )
    item = Entity[Sheet](
        id=e("key"),
        kind="item",
        name="Key",
        brief="key",
        known=True,
        carried_by=e("mara"),
    )
    return RoomWorld[Sheet](
        cast={**places, e("player"): player, e("mara"): companion, e("key"): item},
        ways={e("hall"): (Way(to=e("crypt")),), e("crypt"): (Way(to=e("hall")),)},
        player_id=e("player"),
        companions=[e("mara")],
        threads={"escape": Thread(id="escape", title="Escape")},
        visits=[RoomVisit(place=e("hall"))],
    )


def test_move_reveals_destination_and_back_way_and_brings_companion() -> None:
    world = _world()
    move(world, e("crypt"))
    assert world.current.id == e("crypt")
    assert world.require(e("crypt")).known
    outward = world.way(e("hall"), e("crypt"))
    back = world.way(e("crypt"), e("hall"))
    assert outward is not None and outward.known
    assert back is not None and back.known
    assert world.require(e("mara")).carried_by == e("crypt")
    assert frontier(world) == 0


def test_rooms_drop_and_death_reparent_items_to_the_current_place() -> None:
    world = _world()
    move(world, e("crypt"))
    apply_change(world, MoveItem(verb="move_item", item_id=e("key"), to=e("place")), lambda: None)
    assert world.require(e("key")).carried_by == e("crypt")
    apply_change(world, Kill(verb="kill", actor_id=e("mara")), lambda: None)
    assert world.require(e("mara")).trait("dead") == Trait(id="dead", name="Dead")


def test_holder_cycles_are_rejected() -> None:
    place = Entity[Sheet](id=e("hall"), kind="place", name="Hall", brief="hall")
    player = Entity[Sheet](
        id=e("player"),
        kind="actor",
        name="Player",
        brief="player",
        known=True,
        carried_by=e("hall"),
    )
    actor = Entity[Sheet](id=e("a"), kind="actor", name="A", brief="a", carried_by=e("item"))
    item = Entity[Sheet](id=e("item"), kind="item", name="Item", brief="item", carried_by=e("a"))
    with pytest.raises(ValueError, match="inside itself"):
        RoomWorld[Sheet](
            cast={e("hall"): place, e("player"): player, e("a"): actor, e("item"): item},
            ways={},
            player_id=e("player"),
            visits=[RoomVisit(place=e("hall"))],
        )


def test_map_bar_requires_shortcut_lock_hidden_and_reachability() -> None:
    cast = {
        e(name): Entity[Sheet](id=e(name), kind="place", name=name, brief=name, known=name == "a")
        for name in ("a", "b", "c", "d")
    }
    cast[e("secret")] = Entity[Sheet](
        id=e("secret"), kind="item", name="Secret", brief="secret", carried_by=e("a")
    )
    draft = MapDraft[Sheet](
        cast=cast,
        start=e("a"),
        ways={
            e("a"): (Way(to=e("b"), known=True), Way(to=e("c"), locked=True)),
            e("b"): (Way(to=e("c")),),
            e("c"): (Way(to=e("a")), Way(to=e("d"))),
            e("d"): (Way(to=e("a")),),
        },
        threads={"escape": Thread(id="escape", title="Escape")},
    )
    assert map_refusal(draft) is None


def test_worldsmith_prompt_asset_is_loaded_into_map_prompt() -> None:
    prompt = render_map("", "", MapDraft[Sheet])

    assert "For an opening map" in prompt
    assert "For an extension" in prompt
