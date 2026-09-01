import pytest
from pydantic import BaseModel

from aidm.core.entities import EntityId
from aidm.kits.entities import Entity
from aidm.kits.rooms.boundary import frontier
from aidm.kits.rooms.state import RoomVisit, RoomWorld, Way
from aidm.kits.rooms.worldsmith import (
    MapDraft,
    apply_extension,
    extension_refusal,
)


class Sheet(BaseModel):
    pass


def e(value: str) -> EntityId:
    return EntityId(value)


def world(*, orphan: bool = False) -> RoomWorld[Sheet]:
    cast = {
        e(name): Entity[Sheet](
            id=e(name), kind="place", name=name, brief=name, known=name == "hall"
        )
        for name in ("hall", "crypt", "vault")
    }
    cast[e("player")] = Entity[Sheet](
        id=e("player"),
        kind="actor",
        name="Player",
        brief="hero",
        known=True,
        carried_by=e("hall"),
    )
    if orphan:
        cast[e("orphan")] = Entity[Sheet](
            id=e("orphan"), kind="place", name="Orphan", brief="orphan"
        )
    ways = {
        e("hall"): (Way(to=e("crypt"), known=True),),
        e("crypt"): (Way(to=e("vault")),),
        e("vault"): (Way(to=e("hall")),),
    }
    return RoomWorld[Sheet](
        cast=cast,
        ways=ways,
        player_id=e("player"),
        visits=[RoomVisit(place=e("hall"))],
    )


def region() -> MapDraft[Sheet]:
    cast = {
        e(name): Entity[Sheet](id=e(name), kind="place", name=name, brief=name)
        for name in ("garden", "tower", "well")
    }
    cast[e("relic")] = Entity[Sheet](
        id=e("relic"), kind="item", name="Relic", brief="relic", carried_by=e("garden")
    )
    return MapDraft[Sheet](
        cast=cast,
        ways={
            e("garden"): (Way(to=e("tower")),),
            e("tower"): (Way(to=e("well")),),
            e("well"): (Way(to=e("garden")),),
        },
        start=e("garden"),
    )


def test_extension_joins_hidden_region_without_moving_player() -> None:
    current = world()
    apply_extension(current, region())

    assert current.current.id == e("hall")
    assert current.require(e("garden")).known is False
    assert current.way(e("hall"), e("garden")) == Way(to=e("garden"))
    assert frontier(current) == 2


def test_extension_bar_requires_reachability_and_hidden_content() -> None:
    draft = region()
    draft.ways[e("tower")] = ()
    draft.cast[e("relic")].known = True

    refusal = extension_refusal(draft, world())

    assert refusal is not None
    assert "places no walk" in refusal
    assert "hidden" in refusal


def test_extension_rechecks_reachability_of_the_existing_graph() -> None:
    with pytest.raises(ValueError, match="Orphan|orphan"):
        apply_extension(world(orphan=True), region())
