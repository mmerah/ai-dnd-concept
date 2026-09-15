from collections.abc import Iterable, Iterator
from typing import Self

from pydantic import Field, model_validator

from aidm.core.entities import Mutable, Refusal, Slug, check_unique, parse
from aidm.core.facts import Fact
from aidm.core.prompt import lines_of
from aidm.engines.base import IS_DEAD, PLAYER_ID, UNKNOWN_ID, Person, Thing, World, check_filing

NOTHING_OFFSCREEN = "no time has passed offscreen; call this only while ELSEWHERE is shown"
MOVES_OFFSCREEN = "something moves where the player cannot see"
MOVED_CARD = "Elsewhere, something moves."


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


class Dungeon[N: Dweller](Mutable):
    places: dict[Slug, Place] = Field(default_factory=dict)
    ways: dict[Slug, list[Way]] = Field(default_factory=dict)
    npcs: dict[Slug, N] = Field(default_factory=dict)
    items: dict[Slug, Prop] = Field(default_factory=dict)
    arc: str = Field(
        default="",
        description="What is really going on in this map: secrets, what can come, and what ties "
        "one hidden thing to another. The player never reads it.",
    )

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        check_filing(self.places)
        check_filing(self.npcs)
        check_filing(self.items)
        check_unique(
            "ids across places, npcs and items", (*self.places, *self.npcs, *self.items, PLAYER_ID)
        )
        for npc in self.npcs.values():
            if npc.place not in self.places:
                raise ValueError(f"{npc.name} is in no place: {npc.place!r}")
        # An authored item may already start `on` the player, who exists in no dict here.
        holders = {*self.npcs, *self.places, PLAYER_ID}
        for item in self.items.values():
            if item.on not in holders:
                raise ValueError(f"{item.name} is on nothing: {item.on!r}")
            if item.on == PLAYER_ID and not item.known:
                raise ValueError(f"{item.name} is on the player but unknown to them")
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

    def things_at(self, place_id: Slug) -> Iterator[N | Prop]:
        npcs = list(self.at(place_id))
        yield from npcs
        for holder in (place_id, *(npc.id for npc in npcs)):
            yield from self.carried(holder)

    def reachable(self, start: Slug) -> set[Slug]:
        reached = {start}
        pending = [start]
        while pending:
            current = pending.pop()
            for way in self.ways.get(current, ()):
                if way.to not in reached:
                    reached.add(way.to)
                    pending.append(way.to)
        return reached

    def add_way(self, from_id: Slug, to_id: Slug, *, known: bool) -> None:
        self.ways.setdefault(from_id, []).append(Way(to=to_id, known=known))


class MapDraft[N: Dweller](Dungeon[N]):
    """A map: places, the ways between them, and the npcs and items in them."""

    start: Slug = Field(description="Exact id of the place this map starts from.")


class RegionDraft[N: Dweller](MapDraft[N]):
    recap: str = Field(
        min_length=1,
        description="One paragraph on the part of the map the player leaves behind: what they "
        "did there, cost, learned and missed.",
    )


class RoomWorld[N: Dweller, P: Person](Dungeon[N], World[N, P]):
    visits: list[Slug] = Field(min_length=1)

    @model_validator(mode="after")
    def _playable(self) -> Self:
        if not self.player.known:
            raise ValueError("the player is unknown to themselves")
        for place_id in self.visits:
            self.require_place(place_id)
        for member_id in self.party:
            npc = self.npcs[member_id]  # the base validator has proven every party id a known npc
            if npc.place != self.current.id:
                raise ValueError(f"{member_id!r} travels with the player but is not at their place")
        return self

    @classmethod
    def opening(cls, draft: MapDraft[N], player: P, items: Iterable[Prop], source: str) -> Self:
        return parse(
            cls,
            {
                "places": draft.places,
                "ways": draft.ways,
                "npcs": draft.npcs,
                "items": {**draft.items, **{item.id: item for item in items}},
                "player": player,
                "visits": [draft.start],
                "source": source,
            },
        )

    @property
    def current(self) -> Place:
        return self.places[self.visits[-1]]

    def frontier(self) -> int:
        return sum(
            not self.require_place(place_id).known for place_id in self.reachable(self.current.id)
        )

    def entity(self, entity_id: Slug) -> Person | Prop | Place | None:
        return self.player if entity_id == self.player.id else super().entity(entity_id)

    def members(self) -> list[N]:
        return [self.npcs[member_id] for member_id in self.party]

    def member_of(self, member_id: Slug) -> N | None:
        return self.npcs.get(member_id)

    def here(self) -> Iterator[P | N]:
        yield self.player
        yield from self.at(self.current.id)

    @property
    def holders_here(self) -> set[Slug]:
        """The player, whoever stands with them, and the place itself."""
        return {self.current.id, *(entity.id for entity in self.here())}

    def require_member_here(self, entity_id: Slug) -> N:
        npc = self.npcs.get(entity_id)
        if npc is None:
            raise Refusal(UNKNOWN_ID.format(entity_id=entity_id))
        if not npc.alive:
            raise Refusal(IS_DEAD.format(name=npc.name))
        if npc.place != self.current.id or not npc.known:
            raise Refusal(f"{npc.name} is not here with the player")
        return npc

    def require_item_here(self, item_id: Slug) -> Prop:
        item = self.require(item_id)
        if not isinstance(item, Prop):
            raise Refusal(f"{item_id!r} is not an item")
        if item.on not in self.holders_here:
            raise Refusal(f"{item.name} is not here with the player")
        return item

    def carried_items(self, holder: Person, item_ids: tuple[Slug, ...]) -> tuple[Prop, ...]:
        check_unique("items", item_ids)
        items: list[Prop] = []
        for item_id in item_ids:
            item = self.items.get(item_id)
            if item is None or item.on != holder.id or not item.known:
                raise Refusal(f"{item_id!r} is not in {holder.name}'s hands")
            items.append(item)
        return tuple(items)

    def leave_party(self, entity_id: Slug) -> list[Fact]:
        npc = self.npcs.get(entity_id)
        if npc is None:
            raise Refusal(UNKNOWN_ID.format(entity_id=entity_id))
        return self.part(npc)

    def _open_way(self, way: Way, destination: Place) -> None:
        """Walked or unlocked, a way is known from both sides."""
        way.known = True
        if (back := self.way(destination.id, self.current.id)) is not None:
            back.known = True

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
        self._open_way(way, destination)
        facts = destination.reveal()
        check_unique("with_ids", with_ids)
        coming: list[N] = []
        for npc_id in with_ids:
            if npc_id == self.player.id:
                raise Refusal("the player already comes along")
            npc = self.require_member_here(npc_id)
            if npc.id in self.party:
                raise Refusal(
                    f"{npc.name} travels with the player and comes along without with_ids"
                )
            coming.append(npc)
        travelers = [*self.members(), *coming]
        for npc in travelers:
            npc.place = destination.id
        self.visits.append(destination.id)
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
        self._open_way(way, destination)
        if (back := self.way(destination.id, here.id)) is not None:
            back.locked = False
        trace = f"the way from {here.mention} to {destination.mention} is unlocked"
        card = f"{destination.name} unlocked"
        return [here.fact(trace, card=card)]

    def reveal_hidden(self, entity_id: Slug) -> list[Fact]:
        entity = self.require(entity_id)
        location = (
            entity.place
            if isinstance(entity, Dweller)
            else entity.on
            if isinstance(entity, Prop)
            else None
        )
        if location not in self.holders_here:
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

    def _offscreen_place(self, place_id: Slug) -> Place:
        away = self.elsewhere()
        found = next((place for place in away if place.id == place_id), None)
        if found is None:
            options = ", ".join(place.name for place in away) or "(none)"
            raise Refusal(f"{place_id!r} is not a place the player has walked away from: {options}")
        return found

    def meanwhile(
        self,
        *,
        dweller_id: Slug | None,
        dweller_to: Slug | None,
        item_id: Slug | None,
        item_to: Slug | None,
        shut_from: Slug | None,
        shut_to: Slug | None,
    ) -> list[Fact]:
        if not self.meanwhile_due:
            raise Refusal(NOTHING_OFFSCREEN)
        facts: list[Fact] = []
        if dweller_id is not None and dweller_to is not None:
            npc = self.npcs.get(dweller_id)
            if npc is None:
                raise Refusal(UNKNOWN_ID.format(entity_id=dweller_id))
            if not npc.alive:
                raise Refusal(IS_DEAD.format(name=npc.name))
            if npc.place == self.current.id:
                raise Refusal(f"{npc.name} stands with the player; that is not offscreen")
            destination = self._offscreen_place(dweller_to)
            walked = self.way(npc.place, destination.id)
            if walked is None or walked.locked:
                origin = self.require_place(npc.place).name
                raise Refusal(f"no unlocked way leads from {origin} to {destination.name}")
            npc.place = destination.id
            facts.append(Fact(trace=f"{npc.name} walks to {destination.name}"))
        if item_id is not None and item_to is not None:
            item = self.items.get(item_id)
            if item is None:
                raise Refusal(UNKNOWN_ID.format(entity_id=item_id))
            if item.on in self.holders_here:
                raise Refusal(f"{item.name} is here with the player")
            where = self._offscreen_place(item_to)
            if item.on == where.id:
                raise Refusal(f"{item.name} is already there")
            item.on = where.id
            facts.append(Fact(trace=f"{item.name} moves to {where.name}"))
        if shut_from is not None and shut_to is not None:
            start = self.require_place(shut_from)
            end = self.require_place(shut_to)
            if self.current.id in (start.id, end.id):
                raise Refusal("a way at the player's place cannot shut offscreen")
            shut = self.way(start.id, end.id)
            if shut is None:
                raise Refusal(f"no way leads from {start.name} to {end.name}")
            if shut.locked:
                raise Refusal(f"the way from {start.name} to {end.name} is already shut")
            if not shut.known:
                raise Refusal(f"the player has not found the way from {start.name} to {end.name}")
            shut.locked = True
            if (back := self.way(end.id, start.id)) is not None:
                back.locked = True
            facts.append(Fact(trace=f"the way from {start.name} to {end.name} shuts"))
        facts.append(Fact(trace=MOVES_OFFSCREEN, told=True, card=MOVED_CARD))
        self.disarm()
        return facts

    def kill(self, entity_id: Slug) -> list[Fact]:
        actor: P | N = (
            self.player if entity_id == self.player.id else self.require_member_here(entity_id)
        )
        if not actor.alive:
            raise Refusal(f"{actor.name} is already dead")
        facts: list[Fact] = []
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
        """No check runs here: every caller refuses first, so a refused region leaves it alone."""
        anchor_id = self.current.id
        self.places.update(region.places)
        # Copied: the anchor ways appended below must not land in the draft's own lists.
        self.ways.update({key: [*ways] for key, ways in region.ways.items()})
        self.npcs.update(region.npcs)
        self.items.update(region.items)
        self.arc = "\n".join(part for part in (self.arc, region.arc) if part)
        self.add_way(anchor_id, start, known=False)
        self.add_way(start, anchor_id, known=False)

    def line(self, entity: P | N | Prop) -> str:
        return entity.line(rows=self.sheet_rows()) if entity.id == self.player.id else entity.line()

    def others(self) -> Iterator[N]:
        return (npc for npc in self.at(self.current.id) if npc.known and npc.id not in self.party)

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

    def elsewhere_lines(self) -> str:
        return lines_of(self._offscreen_line(place) for place in self.elsewhere())

    def _offscreen_line(self, place: Place) -> str:
        standing = ", ".join(
            thing.tag
            for thing in self.things_at(place.id)
            if not isinstance(thing, Person) or thing.alive
        )
        ways = ", ".join(
            f"{self.require_place(way.to).tag}{'' if way.known else ' (unfound)'}"
            for way in self.ways.get(place.id, ())
            if not way.locked
        )
        return f"- {place.tag} — {standing or '(nobody, nothing)'}; ways: {ways or '(none)'}"

    def elsewhere(self) -> list[Place]:
        """Visited, de-duplicated in order, minus where the player stands."""
        return [place for place in self._visited() if place.id != self.current.id]

    def can_move_offscreen(self) -> bool:
        """Something the master is shown offscreen that one of the three powers could touch."""
        here = self.current.id
        away = {place.id for place in self.elsewhere()}
        if not away:
            return False
        offscreen = {npc.id for npc in self.npcs.values() if npc.place in away}
        if any(item.on in away or item.on in offscreen for item in self.items.values()):
            return True
        walkers = {npc.place for npc in self.npcs.values() if npc.alive and npc.place in away}
        return any(
            (way.to in away and place_id in walkers) or (way.known and way.to != here)
            for place_id in away
            for way in self.ways.get(place_id, ())
            if not way.locked
        )

    def _visited(self) -> list[Place]:
        """Every visited place, de-duplicated in order of first visit."""
        seen: dict[Slug, Place] = {}
        for place_id in self.visits:
            seen.setdefault(place_id, self.require_place(place_id))
        return list(seen.values())

    def map_so_far(self) -> str:
        lines: list[str] = []
        for place in self._visited():
            known_ways = ", ".join(
                self.require_place(way.to).name for way in self.ways.get(place.id, ()) if way.known
            )
            here = ", ".join(
                f"{entity.tag} ({entity.met_label})" for entity in self.things_at(place.id)
            )
            lines.append(
                f"{place.tag} — {place.description}\n  known ways out: {known_ways or '(none)'}"
                f"\n  here: {here or '(nobody, nothing)'}"
            )
        lines.append("ids in use: " + ", ".join(sorted((*self.places, *self.npcs, *self.items))))
        return "\n".join(lines)
