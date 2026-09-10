from collections.abc import Iterable, Iterator
from typing import Self

from pydantic import Field, model_validator

from aidm.core.entities import Mutable, Refusal, Slug, check_unique, parse
from aidm.core.facts import Fact
from aidm.core.play import Exchange, SceneRecord
from aidm.core.prompt import lines_of
from aidm.core.views import Pairs
from aidm.engines.base import IS_DEAD, PLAYER_ID, UNKNOWN_ID, Person, Thing, World, check_filing


class Dweller(Person):
    place: Slug


class Prop(Thing):
    on: Slug


class Place(Thing):
    description: str = Field(min_length=1)


class Way(Mutable):
    """One directed passage from the place under which it is filed."""

    to: Slug
    known: bool = False
    locked: bool = False


class Visit(Mutable):
    place: Slug
    exchanges: list[Exchange] = Field(default_factory=list)


class Dungeon[N: Dweller](Mutable):
    places: dict[Slug, Place] = Field(default_factory=dict)
    ways: dict[Slug, list[Way]] = Field(default_factory=dict)
    npcs: dict[Slug, N] = Field(default_factory=dict)
    items: dict[Slug, Prop] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        check_filing(self.places)
        check_filing(self.npcs)
        check_filing(self.items)
        check_unique("ids across places, npcs and items", (*self.places, *self.npcs, *self.items))
        for npc in self.npcs.values():
            if npc.place not in self.places:
                raise ValueError(f"{npc.name} is in no place: {npc.place!r}")
        # An authored item may already start `on` the player, who exists in no dict here.
        holders = {*self.npcs, *self.places, PLAYER_ID}
        for item in self.items.values():
            if item.on not in holders:
                raise ValueError(f"{item.name} is on nothing: {item.on!r}")
        for from_id, ways in self.ways.items():
            if from_id not in self.places:
                raise ValueError(f"ways are filed under {from_id!r}, which is not a place")
            check_unique(f"ways out of {from_id!r}", (way.to for way in ways))
            for way in ways:
                if way.to not in self.places:
                    raise ValueError(
                        f"a way from {from_id!r} leads to {way.to!r}, which is not a place"
                    )
                if way.to == from_id:
                    raise ValueError(f"a way from {from_id!r} cannot lead back to itself")
        return self

    def entity(self, entity_id: Slug) -> Person | Prop | Place | None:
        return self.places.get(entity_id) or self.npcs.get(entity_id) or self.items.get(entity_id)

    def require(self, entity_id: Slug) -> Person | Prop | Place:
        entity = self.entity(entity_id)
        if entity is None:
            raise Refusal(UNKNOWN_ID.format(entity_id=entity_id))
        return entity

    def require_place(self, entity_id: Slug) -> Place:
        entity = self.require(entity_id)
        if not isinstance(entity, Place):
            raise Refusal(f"{entity_id!r} is not a place")
        return entity

    def way(self, from_id: Slug, to_id: Slug) -> Way | None:
        return next((way for way in self.ways.get(from_id, ()) if way.to == to_id), None)

    def at(self, place_id: Slug) -> Iterator[N]:
        return (npc for npc in self.npcs.values() if npc.place == place_id)

    def carried(self, holder_id: Slug) -> Iterator[Prop]:
        """A place holds what lies loose in it, the same way an npc holds what it carries."""
        return (item for item in self.items.values() if item.on == holder_id)

    def frontier(self) -> int:
        return len(
            {
                way.to
                for from_id, ways in self.ways.items()
                if self.require_place(from_id).known
                for way in ways
                if not self.require_place(way.to).known
            }
        )

    def reachable(self, start: Slug) -> set[Slug]:
        return _walk(self.ways, start)

    def add_way(self, from_id: Slug, to_id: Slug, *, known: bool) -> None:
        self.ways.setdefault(from_id, []).append(Way(to=to_id, known=known))


class MapDraft[N: Dweller](Dungeon[N]):
    """A map: places, the ways between them, and the npcs and items in them."""

    start: Slug = Field(description="Exact id of the place this map starts from.")


class RoomCanon[N: Dweller](Dungeon[N]):
    start: Slug
    source: str = ""

    @model_validator(mode="after")
    def _startable(self) -> Self:
        if not self.require_place(self.start).known:
            raise ValueError("the starting place must be known to the player")
        return self


class RoomWorld[N: Dweller, P: Person](Dungeon[N], World[P]):
    visits: list[Visit] = Field(min_length=1)

    @model_validator(mode="after")
    def _playable(self) -> Self:
        if not self.player.known:
            raise ValueError("the player is unknown to themselves")
        for visit in self.visits:
            self.require_place(visit.place)
        check_unique("party", self.party)
        for member_id in self.party:
            npc = self.npcs.get(member_id)
            if npc is None or not npc.known:
                raise ValueError(f"{member_id!r} travels with the player but is not a known npc")
            if not npc.alive:
                raise ValueError(f"{member_id!r} is dead and cannot travel with the player")
            if npc.place != self.current.id:
                raise ValueError(f"{member_id!r} travels with the player but is not at their place")
        return self

    @classmethod
    def begin(cls, canon: RoomCanon[N], player: P, items: Iterable[Prop]) -> Self:
        return parse(
            cls,
            {
                "places": canon.places,
                "ways": canon.ways,
                "npcs": canon.npcs,
                "items": {**canon.items, **{item.id: item for item in items}},
                "player": player,
                "visits": [Visit(place=canon.start)],
                "source": canon.source,
            },
        )

    @property
    def current(self) -> Place:
        return self.places[self.visits[-1].place]

    @property
    def visit(self) -> Visit:
        return self.visits[-1]

    def entity(self, entity_id: Slug) -> Person | Prop | Place | None:
        return self.player if entity_id == self.player.id else super().entity(entity_id)

    def members(self) -> list[N]:
        return [self.npcs[member_id] for member_id in self.party]

    def here(self) -> Iterator[P | N]:
        yield self.player
        yield from self.at(self.current.id)

    def require_npc_here(self, entity_id: Slug) -> N:
        npc = self.npcs.get(entity_id)
        if npc is None:
            raise Refusal(UNKNOWN_ID.format(entity_id=entity_id))
        if not npc.alive:
            raise Refusal(IS_DEAD.format(name=npc.name))
        if npc.place != self.current.id:
            raise Refusal(f"{npc.name} is not here with the player")
        return npc

    def require_item_here(self, item_id: Slug) -> Prop:
        item = self.require(item_id)
        if not isinstance(item, Prop):
            raise Refusal(f"{item_id!r} is not an item")
        holders = {self.current.id, *(entity.id for entity in self.here())}
        if item.on not in holders:
            raise Refusal(f"{item.name} is not here with the player")
        return item

    def carried_items(self, holder: Person, item_ids: tuple[Slug, ...]) -> tuple[Prop, ...]:
        check_unique("items", item_ids)
        items: list[Prop] = []
        for item_id in item_ids:
            item = self.items.get(item_id)
            if item is None or item.on != holder.id:
                raise Refusal(f"{item_id!r} is not in {holder.name}'s hands")
            items.append(item)
        return tuple(items)

    def join_party(self, entity_id: Slug) -> list[Fact]:
        return self.join(self.require_npc_here(entity_id))

    def leave_party(self, entity_id: Slug) -> list[Fact]:
        npc = self.npcs.get(entity_id)
        if npc is None:
            raise Refusal(UNKNOWN_ID.format(entity_id=entity_id))
        return self.part(npc)

    def move(self, to_id: Slug, with_ids: tuple[Slug, ...]) -> list[Fact]:
        here = self.current
        destination = self.require_place(to_id)
        way = self.way(here.id, destination.id)
        if way is None:
            options = ", ".join(
                self.require_place(other.to).name for other in self.ways.get(here.id, ())
            )
            raise Refusal(
                f"no way leads from {here.name} to {destination.name}; ways out: "
                f"{options or '(none)'}"
            )
        if way.locked:
            raise Refusal(f"the way to {destination.name} is locked and must be dealt with first")
        way.known = True
        back = self.way(destination.id, here.id)
        if back is not None:
            back.known = True
        facts = destination.reveal()
        check_unique("with_ids", with_ids)
        coming: list[N] = []
        for npc_id in with_ids:
            if npc_id == self.player.id:
                raise Refusal("the player already comes along")
            npc = self.require_npc_here(npc_id)
            if npc.id in self.party:
                raise Refusal(
                    f"{npc.name} travels with the player and comes along without with_ids"
                )
            coming.append(npc)
        travelers = [*self.members(), *coming]
        for npc in travelers:
            npc.place = destination.id
        self.visits.append(Visit(place=destination.id))
        trace = f"the player arrives at {destination.mention}"
        if travelers:
            names = " and ".join(npc.name for npc in travelers)
            verb = "comes" if len(travelers) == 1 else "come"
            trace += f", and {names} {verb} along"
        facts.append(destination.fact(trace, card=f"Arrived at {destination.name}"))
        return facts

    def unlock_way(self, to_id: Slug) -> list[Fact]:
        here = self.current
        destination = self.require_place(to_id)
        way = self.way(here.id, destination.id)
        if way is None:
            raise Refusal(f"no way leads from {here.name} to {destination.name}")
        if not way.locked:
            raise Refusal(f"the way from {here.name} to {destination.name} is not locked")
        way.locked = False
        way.known = True
        back = self.way(destination.id, here.id)
        if back is not None:
            back.known = True
        trace = f"the way from {here.mention} to {destination.mention} is unlocked"
        card = f"{destination.name} unlocked"
        return [here.fact(trace, card=card)]

    def reveal_hidden(self, entity_id: Slug) -> list[Fact]:
        entity = self.require(entity_id)
        holders = {self.current.id, *(member.id for member in self.here())}
        location = (
            entity.place
            if isinstance(entity, Dweller)
            else entity.on
            if isinstance(entity, Prop)
            else None
        )
        if location not in holders:
            raise Refusal(f"{entity.name} is not here with the player")
        found = "found" if isinstance(entity, Prop) else "discovered"
        if entity.known:
            raise Refusal(f"the player has already {found} {entity.name}")
        return entity.reveal(card=f"{entity.name} {found}")

    def move_item(self, item_id: Slug, to: Slug) -> list[Fact]:
        item = self.require_item_here(item_id)
        if to != self.player.id and to != self.current.id:
            npc = next((other for other in self.here() if other.id == to and other.alive), None)
            if npc is None:
                raise Refusal(
                    f"{to!r} cannot hold {item.name}; give the player, a living npc here, or "
                    "this place"
                )
        holder = self.require(to)
        if not holder.known:
            raise Refusal(f"the player has not met {holder.name}; reveal them first")
        if item.on == to:
            raise Refusal(f"{item.name} is already there")
        facts = item.reveal()
        item.on = to
        card = f"Took {item.name}" if to == self.player.id else f"{item.name} → {holder.name}"
        trace = f"{item.mention} moves to {holder.mention}"
        return [*facts, item.fact(trace, card=card)]

    def kill(self, actor: P | N) -> list[Fact]:
        facts = actor.reveal()
        if actor.id in self.party:
            self.party.remove(actor.id)
        actor.alive = False
        dropped = list(self.carried(actor.id))
        for item in dropped:
            item.on = self.current.id
        if dropped:
            fell = ", ".join(item.mention for item in dropped) + " fell loose here"
            facts.append(Fact(trace=fell))
        card = "You are dead" if actor.id == self.player.id else f"{actor.name} is dead"
        facts.append(actor.fact(f"{actor.mention} is dead", card=card))
        return facts

    def attach(self, region: Dungeon[N], start: Slug) -> None:
        """No bar runs here: every caller refuses first, so a refused region leaves it alone."""
        anchor_id = self.current.id
        self.places.update(region.places)
        # Copied: the anchor ways appended below must not land in the draft's own lists.
        self.ways.update({key: [*ways] for key, ways in region.ways.items()})
        self.npcs.update(region.npcs)
        self.items.update(region.items)
        self.add_way(anchor_id, start, known=False)
        self.add_way(start, anchor_id, known=False)

    def line(self, entity: P | N | Prop) -> str:
        return entity.line(rows=self.sheet_rows()) if entity.id == self.player.id else entity.line()

    def things_at(self, place_id: Slug) -> Iterator[N | Prop]:
        npcs = list(self.at(place_id))
        yield from npcs
        for holder in (place_id, *(npc.id for npc in npcs)):
            yield from self.carried(holder)

    def place_lines(self, *, known: bool) -> str:
        """A member prints under THE PARTY instead; what they carry stays listed here."""
        return lines_of(
            self.line(entity)
            for entity in self.things_at(self.current.id)
            if entity.known == known and entity.id not in self.party
        )

    def ways_lines(self) -> str:
        return lines_of(
            f"- {self.require_place(way.to).tag} — "
            + ("known" if way.known else "unknown")
            + ("; locked" if way.locked else "")
            for way in self.ways.get(self.current.id, ())
        )

    def map_so_far(self) -> str:
        seen: dict[Slug, Place] = {}
        for visit in self.visits:
            seen.setdefault(visit.place, self.require_place(visit.place))
        lines: list[str] = []
        for place in seen.values():
            known_ways = ", ".join(
                self.require_place(way.to).name for way in self.ways.get(place.id, ()) if way.known
            )
            here = ", ".join(f"{e.tag} ({e.met_label})" for e in self.things_at(place.id))
            lines.append(
                f"{place.tag} — {place.description}\n  known ways out: {known_ways or '(none)'}"
                f"\n  here: {here or '(nobody, nothing)'}"
            )
        lines.append("ids in use: " + ", ".join(sorted((*self.places, *self.npcs, *self.items))))
        return "\n".join(lines)

    def sheet_rows(self) -> Pairs:
        """Overridable: a rule may amend a row."""
        return self.player.rows()

    def record(self, exchange: Exchange) -> None:
        self.visit.exchanges.append(exchange)

    def records(self) -> tuple[SceneRecord, ...]:
        records: list[SceneRecord] = []
        for visit in (*(v for v in self.visits[:-1] if v.exchanges), self.visit):
            place = self.require_place(visit.place)
            records.append(
                SceneRecord(title=place.name, focus=place.brief, exchanges=tuple(visit.exchanges))
            )
        return tuple(records)


def _walk(ways: dict[Slug, list[Way]], start: Slug) -> set[Slug]:
    reached = {start}
    pending = [start]
    while pending:
        current = pending.pop()
        for way in ways.get(current, ()):
            if way.to not in reached:
                reached.add(way.to)
                pending.append(way.to)
    return reached
