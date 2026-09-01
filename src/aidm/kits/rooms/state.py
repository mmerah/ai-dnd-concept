from collections.abc import Iterator
from typing import Self

from pydantic import BaseModel, Field, model_validator

from aidm.core.entities import DEAD, CheckedEntityId, EntityId, Mutable, Slug, require_unique
from aidm.core.facts import Fact
from aidm.core.play import Exchange
from aidm.kits.entities import Entity, Kind, Thread, check_filing, labeled
from aidm.kits.entities import carried_by as _carried_by
from aidm.kits.entities import require as _require
from aidm.kits.entities import require_kind as _require_entity_kind
from aidm.kits.entities import reveal as _reveal


class Way(Mutable):
    """One directed passage from the place under which it is filed."""

    to: CheckedEntityId
    known: bool = False
    locked: bool = False


class RoomVisit(Mutable):
    place: CheckedEntityId
    exchanges: list[Exchange] = Field(default_factory=list)


class RoomCanon[S: BaseModel](Mutable):
    """An authored map before the played character is placed at its start."""

    cast: dict[EntityId, Entity[S]] = Field(default_factory=dict)
    ways: dict[EntityId, tuple[Way, ...]] = Field(default_factory=dict)
    start: CheckedEntityId
    threads: dict[Slug, Thread] = Field(default_factory=dict)
    source: str = ""

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        check_filing(self.cast, self.threads)
        _check_placement(self.cast)
        _check_ways(self.cast, self.ways)
        _require_kind(self.cast, self.start, "place")
        return self


class RoomWorld[S: BaseModel](Mutable):
    """An authored graph whose entity holders express placement inside its places."""

    cast: dict[EntityId, Entity[S]] = Field(default_factory=dict)
    ways: dict[EntityId, tuple[Way, ...]] = Field(default_factory=dict)
    player_id: CheckedEntityId
    companions: list[EntityId] = Field(default_factory=list)
    threads: dict[Slug, Thread] = Field(default_factory=dict)
    visits: list[RoomVisit] = Field(min_length=1)
    source: str = ""

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        check_filing(self.cast, self.threads)
        _check_placement(self.cast)
        _check_ways(self.cast, self.ways)
        player = _require_kind(self.cast, self.player_id, "actor")
        if not player.known:
            raise ValueError("the player is unknown to themselves")
        place = _holder_place(self.cast, player)
        if place is None:
            raise ValueError("the player is not held by a place")
        require_unique("companions", self.companions)
        if self.player_id in self.companions:
            raise ValueError("the player cannot travel with themselves")
        for member_id in self.companions:
            member = _require_kind(self.cast, member_id, "actor")
            if not member.known:
                raise ValueError(f"{member_id!r} travels with the player without being met")
            if member.trait(DEAD) is not None:
                raise ValueError(f"{member_id!r} is dead and cannot travel with the player")
        for visit in self.visits:
            _require_kind(self.cast, visit.place, "place")
        if self.visits[-1].place != place.id:
            raise ValueError("the latest visit is not the player's current place")
        return self

    def require(self, entity_id: EntityId) -> Entity[S]:
        return _require(self.cast, entity_id)

    def require_kind(self, entity_id: EntityId, kind: Kind) -> Entity[S]:
        return _require_entity_kind(self.cast, entity_id, kind)

    @property
    def player(self) -> Entity[S]:
        return self.require_kind(self.player_id, "actor")

    @property
    def current(self) -> Entity[S]:
        place = self.location_of(self.player)
        if place is None:
            raise ValueError("the player is not held by a place")
        return place

    @property
    def visit(self) -> RoomVisit:
        return self.visits[-1]

    def way(self, from_id: EntityId, to_id: EntityId) -> Way | None:
        return next((one for one in self.ways.get(from_id, ()) if one.to == to_id), None)

    def location_of(self, entity: Entity[S]) -> Entity[S] | None:
        return _holder_place(self.cast, entity)

    def at(self, place_id: EntityId) -> Iterator[Entity[S]]:
        return (
            one
            for one in self.cast.values()
            if one.kind != "place"
            and (place := self.location_of(one)) is not None
            and place.id == place_id
        )

    def here(self) -> Iterator[Entity[S]]:
        return self.at(self.current.id)

    def carried_by(self, holder_id: EntityId) -> Iterator[Entity[S]]:
        return _carried_by(self.cast, holder_id)

    def label(self, entity: Entity[S]) -> str:
        return labeled(entity, self.player_id)

    def reveal(self, entity: Entity[S]) -> list[Fact]:
        return _reveal(entity, self.player_id)

    def require_actor_here(self, actor_id: EntityId) -> Entity[S]:
        actor = self.require_kind(actor_id, "actor")
        if actor.trait(DEAD) is not None:
            raise ValueError(f"{actor.name} is dead; they take no further part.")
        location = self.location_of(actor)
        if location is None or location.id != self.current.id:
            raise ValueError(
                f"{actor_id!r} is not here with the player. "
                "Bring them here first, or act on who is here."
            )
        return actor

    def exchanges(self) -> tuple[Exchange, ...]:
        return tuple(one for visit in self.visits for one in visit.exchanges)


def _check_placement[S: BaseModel](cast: dict[EntityId, Entity[S]]) -> None:
    for one in cast.values():
        _check_chain(cast, one)
        holder = None if one.carried_by is None else cast[one.carried_by]
        if one.kind == "place":
            if holder is not None:
                raise ValueError(f"place {one.id!r} cannot be held by anything")
        elif one.kind == "actor":
            if holder is None or holder.kind != "place":
                held_by = "nothing" if holder is None else f"a {holder.kind}"
                raise ValueError(f"actor {one.id!r} is held by {held_by}, not a place")
        elif one.kind in ("item", "prop"):
            if holder is None or holder.kind not in ("actor", "place"):
                held_by = "nothing" if holder is None else f"a {holder.kind}"
                raise ValueError(
                    f"{one.kind} {one.id!r} is held by {held_by}, not an actor or place"
                )
        else:
            raise ValueError(f"rooms cannot place {one.kind} {one.id!r}")


def _check_chain[S: BaseModel](cast: dict[EntityId, Entity[S]], entity: Entity[S]) -> None:
    seen = {entity.id}
    current = entity
    while current.carried_by is not None:
        if current.carried_by in seen:
            raise ValueError(f"{entity.id!r} is inside itself through its holders")
        current = cast[current.carried_by]
        seen.add(current.id)


def _check_ways[S: BaseModel](
    cast: dict[EntityId, Entity[S]], ways: dict[EntityId, tuple[Way, ...]]
) -> None:
    for from_id, leaving in ways.items():
        _require_kind(cast, from_id, "place")
        require_unique(f"ways from {from_id!r}", (one.to for one in leaving))
        for way in leaving:
            _require_kind(cast, way.to, "place")
            if way.to == from_id:
                raise ValueError(f"a way from {from_id!r} leads back to itself")


def _require_kind[S: BaseModel](
    cast: dict[EntityId, Entity[S]], entity_id: EntityId, kind: Kind
) -> Entity[S]:
    one = cast.get(entity_id)
    if one is None:
        raise ValueError(f"unknown id {entity_id!r}")
    if one.kind != kind:
        raise ValueError(f"{entity_id!r} is a {one.kind}, not a {kind}")
    return one


def _holder_place[S: BaseModel](
    cast: dict[EntityId, Entity[S]], entity: Entity[S]
) -> Entity[S] | None:
    current = entity
    while current.kind != "place":
        if current.carried_by is None:
            return None
        current = cast[current.carried_by]
    return current
