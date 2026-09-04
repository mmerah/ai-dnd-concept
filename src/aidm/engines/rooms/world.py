from collections.abc import Iterable, Iterator, Mapping
from typing import Self

from pydantic import Field, model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Mutable, Refusal, parse, require_unique
from aidm.core.facts import Fact
from aidm.core.play import Exchange, SceneRecord
from aidm.core.views import Rows, lines_of
from aidm.engines.base import IS_DEAD, PLAYER_ID, UNKNOWN_ID, Person, Thing, check_filing
from aidm.engines.hub import Board, Campaign, Job, World, walk_start


class Dweller(Person):
    """Anyone who stands in a place; a room engine's npc adds its own stats."""

    place: CheckedEntityId


class Item(Thing):
    on: CheckedEntityId


class Place(Thing):
    description: str = Field(min_length=1)


class Way(Mutable):
    """One directed passage from the place under which it is filed."""

    to: CheckedEntityId
    known: bool = False
    locked: bool = False


class Visit(Mutable):
    place: CheckedEntityId
    exchanges: list[Exchange] = Field(default_factory=list)
    recap: str = ""
    job: str = ""  # the campaign job this visit walks, by title; empty at the tavern


class Dungeon[N: Dweller](Mutable):
    """The map and everything in it; the holder matrix is in the types."""

    places: dict[EntityId, Place] = Field(default_factory=dict)
    ways: dict[EntityId, list[Way]] = Field(default_factory=dict)
    npcs: dict[EntityId, N] = Field(default_factory=dict)
    items: dict[EntityId, Item] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        check_filing(self.places)
        check_filing(self.npcs)
        check_filing(self.items)
        require_unique("ids across places, npcs and items", (*self.places, *self.npcs, *self.items))
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
            require_unique(f"ways out of {from_id!r}", (way.to for way in ways))
            for way in ways:
                if way.to not in self.places:
                    raise ValueError(
                        f"a way from {from_id!r} leads to {way.to!r}, which is not a place"
                    )
                if way.to == from_id:
                    raise ValueError(f"a way from {from_id!r} cannot lead back to itself")
        return self

    def entity(self, entity_id: EntityId) -> Person | Item | Place | None:
        return self.places.get(entity_id) or self.npcs.get(entity_id) or self.items.get(entity_id)

    def require(self, entity_id: EntityId) -> Person | Item | Place:
        entity = self.entity(entity_id)
        if entity is None:
            raise Refusal(UNKNOWN_ID.format(entity_id=entity_id))
        return entity

    def require_place(self, entity_id: EntityId) -> Place:
        entity = self.require(entity_id)
        if not isinstance(entity, Place):
            raise Refusal(f"{entity_id!r} is not a place")
        return entity

    def way(self, from_id: EntityId, to_id: EntityId) -> Way | None:
        return next((way for way in self.ways.get(from_id, ()) if way.to == to_id), None)

    def at(self, place_id: EntityId) -> Iterator[N]:
        return (npc for npc in self.npcs.values() if npc.place == place_id)

    def carried(self, holder_id: EntityId) -> Iterator[Item]:
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

    def reachable(self, start: EntityId) -> set[EntityId]:
        return _walk(self.ways, start)

    def has_shortcut(self) -> bool:
        return any(
            direct.to in _walk({**self.ways, start: [w for w in leaving if w is not direct]}, start)
            for start, leaving in self.ways.items()
            for direct in leaving
        )

    def add_way(self, from_id: EntityId, to_id: EntityId, *, known: bool) -> None:
        self.ways.setdefault(from_id, []).append(Way(to=to_id, known=known))


class RoomCanon[N: Dweller](Dungeon[N]):
    """An authored map before the played character stands at its start."""

    start: CheckedEntityId
    source: str = ""
    campaign: Campaign | None = None

    @model_validator(mode="after")
    def _startable(self) -> Self:
        if not self.require_place(self.start).known:
            raise ValueError("the starting place must be known to the player")
        if self.campaign is not None:
            if self.campaign.place != self.start:
                raise ValueError(
                    f"hub {self.campaign.place!r} is not the starting place {self.start!r}"
                )
            if self.campaign.jobs:
                raise ValueError("an opening with jobs walked")
        return self


class RoomWorld[N: Dweller, P: Person](Dungeon[N], World[P]):
    visits: list[Visit] = Field(min_length=1)

    @model_validator(mode="after")
    def _playable(self) -> Self:
        if not self.player.known:
            raise ValueError("the player is unknown to themselves")
        for visit in self.visits:
            self.require_place(visit.place)
        if (campaign := self.campaign) is not None:
            self.require_place(EntityId(campaign.place))
            if self.visits[0].place != campaign.place:
                raise ValueError(f"visit 0 does not open at hub {campaign.place!r}")
            campaign.check_walk([visit.place for visit in self.visits], self.walked())
        return self

    @classmethod
    def begin(cls, canon: RoomCanon[N], player: P, items: Iterable[Item]) -> Self:
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
                "campaign": canon.campaign,
            },
        )

    @property
    def current(self) -> Place:
        return self.places[self.visits[-1].place]

    @property
    def visit(self) -> Visit:
        return self.visits[-1]

    @property
    def at_hub(self) -> bool:
        return self.campaign is not None and self.current.id == self.campaign.place

    def walked_job(self) -> Job | None:
        """The open job once walked; one taken at the tavern but not walked can still be swapped."""
        job = None if self.campaign is None else self.campaign.open_job()
        return job if job is not None and self.visit.job == job.title else None

    def walked(self) -> list[str]:
        return [visit.job for visit in self.visits]

    def job_visits(self) -> list[Visit]:
        return self.visits if self.campaign is None else self.visits[walk_start(self.walked()) :]

    def walked_places(self) -> tuple[EntityId, ...]:
        """Distinct places the walking span crossed; the current tavern visit is not walked."""
        seen: list[EntityId] = []
        for visit in self.visits[walk_start(self.walked()) : -1]:
            if visit.place not in seen:
                seen.append(visit.place)
        return tuple(seen)

    def entity(self, entity_id: EntityId) -> Person | Item | Place | None:
        return self.player if entity_id == self.player.id else super().entity(entity_id)

    def here(self) -> Iterator[P | N]:
        yield self.player
        yield from self.at(self.current.id)

    def require_npc_here(self, entity_id: EntityId) -> N:
        npc = self.npcs.get(entity_id)
        if npc is None:
            raise Refusal(UNKNOWN_ID.format(entity_id=entity_id))
        if not npc.alive:
            raise Refusal(IS_DEAD.format(name=npc.name))
        if npc.place != self.current.id:
            raise Refusal(f"{npc.name} is not here with the player")
        return npc

    def require_item_here(self, item_id: EntityId) -> Item:
        item = self.require(item_id)
        if not isinstance(item, Item):
            raise Refusal(f"{item_id!r} is not an item")
        holders = {self.current.id, *(entity.id for entity in self.here())}
        if item.on not in holders:
            raise Refusal(f"{item.name} is not here with the player")
        return item

    def carried_items(self, item_ids: tuple[EntityId, ...]) -> tuple[Item, ...]:
        require_unique("items", item_ids)
        items: list[Item] = []
        for item_id in item_ids:
            item = self.items.get(item_id)
            if item is None or item.on != self.player.id:
                raise Refusal(f"{item_id!r} is not in the player's hands")
            items.append(item)
        return tuple(items)

    def move(self, to_id: EntityId, with_ids: tuple[EntityId, ...]) -> list[Fact]:
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
        require_unique("with_ids", with_ids)
        coming: list[N] = []
        for npc_id in with_ids:
            if npc_id == self.player.id:
                raise Refusal("the player already comes along")
            coming.append(self.require_npc_here(npc_id))
        for npc in coming:
            npc.place = destination.id
        job = None if self.campaign is None else self.campaign.open_job()
        self.visits.append(Visit(place=destination.id, job="" if job is None else job.title))
        trace = f"the player arrives at {destination.label}"
        if coming:
            names = " and ".join(npc.name for npc in coming)
            verb = "comes" if len(coming) == 1 else "come"
            trace += f", and {names} {verb} along"
        facts.append(destination.fact("arrived", trace, card=f"Arrived at {destination.name}"))
        return facts

    def unlock_way(self, to_id: EntityId) -> list[Fact]:
        here = self.current
        destination = self.require_place(to_id)
        way = self.way(here.id, destination.id)
        if way is None:
            raise Refusal(f"no way leads from {here.name} to {destination.name}")
        if not way.locked:
            raise Refusal(f"the way from {here.name} to {destination.name} is not locked")
        way.locked = False
        trace = f"the way from {here.label} to {destination.label} is unlocked"
        card = f"{destination.name} unlocked"
        return [here.fact("way_unlocked", trace, narrate=way.known and here.known, card=card)]

    def reveal_hidden(self, entity_id: EntityId) -> list[Fact]:
        entity = self.require(entity_id)
        holders = {self.current.id, *(member.id for member in self.here())}
        location = (
            entity.place
            if isinstance(entity, Dweller)
            else entity.on
            if isinstance(entity, Item)
            else None
        )
        if location not in holders:
            raise Refusal(f"{entity.name} is not here with the player")
        found = "found" if isinstance(entity, Item) else "discovered"
        if entity.known:
            raise Refusal(f"the player has already {found} {entity.name}")
        return entity.reveal(card=f"{entity.name} {found}")

    def move_item(self, item_id: EntityId, to: EntityId) -> list[Fact]:
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
        trace = f"{item.label} moves to {holder.label}"
        return [*facts, item.fact("entity_moved", trace, card=card)]

    def kill(self, actor: P | N) -> list[Fact]:
        """Whatever the dead carried lies loose where they fell, the player's kit included."""
        facts = actor.reveal()
        actor.alive = False
        dropped = list(self.carried(actor.id))
        for item in dropped:
            item.on = self.current.id
        if dropped:
            fell = ", ".join(item.label for item in dropped) + " fell loose here"
            facts.append(Fact(kind="items_dropped", trace=fell))
        card = "You are dead" if actor.id == self.player.id else f"{actor.name} is dead"
        facts.append(actor.fact("actor_killed", f"{actor.label} is dead", card=card))
        return facts

    def attach(
        self, region: Dungeon[N], start: EntityId, *, known: bool, anchor: EntityId | None = None
    ) -> None:
        """No bar runs here: every caller refuses first, so a refused region leaves it alone."""
        anchor_id = self.current.id if anchor is None else anchor
        self.places.update(region.places)
        # Copied: the anchor ways appended below must not land in the draft's own lists.
        self.ways.update({key: [*ways] for key, ways in region.ways.items()})
        self.npcs.update(region.npcs)
        self.items.update(region.items)
        self.add_way(anchor_id, start, known=known)
        self.add_way(start, anchor_id, known=known)

    def apply_extension(
        self, region: Dungeon[N], start: EntityId, *, reopening: Job | None = None
    ) -> Place:
        """At the hub the region is the job's, known, joined at its anchor; away it is hidden."""
        campaign = self.campaign
        if campaign is None or not self.at_hub:
            self.attach(region, start, known=False)
            return self.current
        if campaign.open_job() is not None and self.walked_job() is None:
            campaign.swap_out(self.walked())
        if reopening is not None:
            anchor = self.require_place(EntityId(reopening.place))
            campaign.reopen(reopening)
            self.attach(region, start, known=True, anchor=anchor.id)
            return anchor
        self.attach(region, start, known=True)
        campaign.jobs.append(Job(title=self.places[start].name, place=start, open=True))
        return self.current

    def apply_return(
        self, *, debrief: str, summary: str, recaps: Mapping[EntityId, str], offers: Board
    ) -> Job:
        """Close the walked job, land each recap on that place's last visit, swap the board.
        No bar runs here: every caller refuses first, so a recap missing is a bug."""
        campaign, job = self.campaign, self.walked_job()
        if campaign is None or job is None:
            raise Refusal("no job is open to report")
        span = self.visits[walk_start(self.walked()) : -1]
        for place, visit in {v.place: v for v in span}.items():
            visit.recap = recaps[place]
        job.close(debrief=debrief, summary=summary)
        self.visit.job = ""  # the report closes the span; the tavern visit walks no job
        campaign.board = offers
        return job

    def line(self, entity: P | N | Item) -> str:
        """One card line; the player's sheet is the world's, everyone else's is their own."""
        return entity.line(rows=self.sheet_rows()) if entity.id == self.player.id else entity.line()

    def things_at(self, place_id: EntityId) -> Iterator[N | Item]:
        """Who stands at a place, then what lies there or in their hands."""
        npcs = list(self.at(place_id))
        yield from npcs
        for holder in (place_id, *(npc.id for npc in npcs)):
            yield from self.carried(holder)

    def place_lines(self, *, known: bool) -> str:
        return lines_of(
            self.line(entity) for entity in self.things_at(self.current.id) if entity.known == known
        )

    def ways_lines(self) -> str:
        return lines_of(
            f"- {self.require_place(way.to).tag} — "
            + ("known" if way.known else "unknown")
            + ("; locked" if way.locked else "")
            for way in self.ways.get(self.current.id, ())
        )

    def map_so_far(self) -> str:
        seen: dict[EntityId, Place] = {}
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

    def sheet_rows(self) -> Rows:
        """The player's sheet as the master and the panel print it; a rule may amend a row."""
        return self.player.rows()

    def record(self, exchange: Exchange) -> None:
        self.visit.exchanges.append(exchange)

    def records(self) -> tuple[SceneRecord, ...]:
        records: list[SceneRecord] = []
        for visit in self.visits:
            place = self.require_place(visit.place)
            records.append(
                SceneRecord(
                    title=place.name,
                    focus=place.brief,
                    recap=visit.recap,
                    exchanges=tuple(visit.exchanges),
                    job=visit.job,
                )
            )
        return tuple(records)


def _walk(ways: dict[EntityId, list[Way]], start: EntityId) -> set[EntityId]:
    reached = {start}
    pending = [start]
    while pending:
        current = pending.pop()
        for way in ways.get(current, ()):
            if way.to not in reached:
                reached.add(way.to)
                pending.append(way.to)
    return reached
