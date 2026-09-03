from collections.abc import Iterable, Iterator
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Mutable, Refusal, require_unique, slug
from aidm.core.facts import Fact
from aidm.core.model import Character, Game, Scenario
from aidm.core.play import Exchange, SceneRecord
from aidm.core.views import Rows
from aidm.engines.base import PLAYER_ID, Counter, Person, Thing, check_filing
from aidm.engines.hub import Campaign, Job

Ability = Literal["brute", "skulker", "erudite"]
ABILITIES: tuple[Ability, ...] = ("brute", "skulker", "erudite")
Boost = Literal["health", "inventory"]
HP_START = 10
INVENTORY_START = 8
ABILITY_POINTS = 3
STARTING_ITEMS = 3
type Entity = Goon | Npc | Item | Place


class Npc(Person):
    """Every non-player character, friend or foe: the SRD gives them one shape."""

    place: CheckedEntityId
    # SRD: an NPC's Difficulty Score is also its Health Points, so one counter serves both.
    hp: Counter


class Item(Thing):
    on: CheckedEntityId


class Goon(Person):
    """The played character: the only one with abilities, and the only one who rolls."""

    abilities: dict[Ability, Annotated[int, Field(ge=0)]] = Field(
        default_factory=lambda: dict.fromkeys(ABILITIES, 0), min_length=3, max_length=3
    )
    hp: Counter = Field(default_factory=lambda: Counter(current=HP_START, maximum=HP_START))
    inventory: int = Field(default=INVENTORY_START, ge=0)
    level: int = Field(default=1, ge=1)
    # The starting items by name; `new_game` files them as `Item`s on the player.
    kit: tuple[str, ...] = Field(min_length=STARTING_ITEMS, max_length=STARTING_ITEMS)

    def rows(self) -> Rows:
        return (
            *((ability.capitalize(), str(self.abilities[ability])) for ability in ABILITIES),
            ("Health", str(self.hp)),
            ("Inventory", str(self.inventory)),
            ("Level", str(self.level)),
        )

    def starting_items(self, taken: Iterable[str]) -> tuple[Item, ...]:
        """The kit filed as `Item`s on the player, with ids clear of every id already taken."""
        made = list(taken)
        items: list[Item] = []
        for name in self.kit:
            item_id = EntityId(slug(name, made))
            made.append(item_id)
            items.append(Item(id=item_id, name=name, brief="", known=True, on=PLAYER_ID))
        return tuple(items)


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


class Dungeon(Mutable):
    """The map and everything in it; the holder matrix is in the types."""

    places: dict[EntityId, Place] = Field(default_factory=dict)
    ways: dict[EntityId, list[Way]] = Field(default_factory=dict)
    npcs: dict[EntityId, Npc] = Field(default_factory=dict)
    items: dict[EntityId, Item] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        check_filing(self.places)
        check_filing(self.npcs)
        check_filing(self.items)
        require_unique("ids across places, npcs and items", (*self.places, *self.npcs, *self.items))
        for one in self.npcs.values():
            if one.place not in self.places:
                raise Refusal(f"{one.name} is in no place: {one.place!r}")
        # An authored item may already start `on` the player, who exists in no dict here.
        holders = {*self.npcs, *self.places, PLAYER_ID}
        for item in self.items.values():
            if item.on not in holders:
                raise Refusal(f"{item.name} is on nothing: {item.on!r}")
        for from_id, ways in self.ways.items():
            if from_id not in self.places:
                raise Refusal(f"ways are filed under {from_id!r}, which is not a place")
            require_unique(f"ways out of {from_id!r}", (way.to for way in ways))
            for way in ways:
                if way.to not in self.places:
                    raise Refusal(
                        f"a way from {from_id!r} leads to {way.to!r}, which is not a place"
                    )
                if way.to == from_id:
                    raise Refusal(f"a way from {from_id!r} cannot lead back to itself")
        return self

    def entity(self, entity_id: EntityId) -> Entity | None:
        return self.places.get(entity_id) or self.npcs.get(entity_id) or self.items.get(entity_id)

    def require(self, entity_id: EntityId) -> Entity:
        one = self.entity(entity_id)
        if one is None:
            raise Refusal(f"unknown id {entity_id!r}. Use only ids you were shown.")
        return one

    def require_place(self, entity_id: EntityId) -> Place:
        one = self.require(entity_id)
        if not isinstance(one, Place):
            raise Refusal(f"{entity_id!r} is not a place")
        return one

    def way(self, from_id: EntityId, to_id: EntityId) -> Way | None:
        return next((one for one in self.ways.get(from_id, ()) if one.to == to_id), None)

    def at(self, place_id: EntityId) -> Iterator[Npc]:
        return (one for one in self.npcs.values() if one.place == place_id)

    def carried(self, holder_id: EntityId) -> Iterator[Item]:
        """A place holds what lies loose in it, the same way an npc holds what it carries."""
        return (one for one in self.items.values() if one.on == holder_id)

    def frontier(self) -> int:
        """Count distinct unknown places reachable through ways out of known places."""
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
        """A shortcut is an edge whose destination remains reachable after that edge is removed."""
        return any(
            direct.to in _walk({**self.ways, start: [w for w in leaving if w is not direct]}, start)
            for start, leaving in self.ways.items()
            for direct in leaving
        )

    def add_way(self, from_id: EntityId, to_id: EntityId, *, known: bool) -> None:
        self.ways.setdefault(from_id, []).append(Way(to=to_id, known=known))


class MapCanon(Dungeon):
    """An authored map before the played character stands at its start."""

    start: CheckedEntityId
    source: str = ""
    campaign: Campaign | None = None

    @model_validator(mode="after")
    def _startable(self) -> Self:
        if not self.require_place(self.start).known:
            raise Refusal("the starting place must be known to the player")
        if self.campaign is not None:
            if self.campaign.place != self.start:
                raise Refusal(
                    f"hub {self.campaign.place!r} is not the starting place {self.start!r}"
                )
            if self.campaign.jobs:
                raise Refusal("an opening with jobs walked")
        return self


class TunnelGoonsWorld(Dungeon):
    player: Goon
    visits: list[Visit] = Field(min_length=1)
    source: str = ""
    campaign: Campaign | None = None

    @model_validator(mode="after")
    def _playable(self) -> Self:
        if not self.player.known:
            raise Refusal("the player is unknown to themselves")
        for visit in self.visits:
            self.require_place(visit.place)
        if (campaign := self.campaign) is not None:
            self.require_place(EntityId(campaign.place))
            campaign.check_walked(len(self.visits))
            if self.visits[0].place != campaign.place:
                raise Refusal(f"visit 0 does not open at hub {campaign.place!r}")
        return self

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
        return job if job is not None and job.started is not None else None

    def job_visits(self) -> list[Visit]:
        return self.visits if self.campaign is None else self.campaign.since_start(self.visits)

    def entity(self, entity_id: EntityId) -> Entity | None:
        return self.player if entity_id == self.player.id else super().entity(entity_id)

    def here(self) -> Iterator[Goon | Npc]:
        yield self.player
        yield from self.at(self.current.id)

    def require_npc_here(self, entity_id: EntityId) -> Npc:
        npc = self.npcs.get(entity_id)
        if npc is None:
            raise Refusal(f"unknown id {entity_id!r}. Use only ids you were shown.")
        if not npc.alive:
            raise Refusal(f"{npc.name} is dead; they take no further part.")
        if npc.place != self.current.id:
            raise Refusal(f"{npc.name} is not here with the player")
        return npc

    def require_item_here(self, item_id: EntityId) -> Item:
        item = self.require(item_id)
        if not isinstance(item, Item):
            raise Refusal(f"{item_id!r} is not an item")
        holders = {self.current.id, *(one.id for one in self.here())}
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
                self.require_place(one.to).name for one in self.ways.get(here.id, ())
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
        coming: list[Npc] = []
        for npc_id in with_ids:
            if npc_id == self.player.id:
                raise Refusal("the player already comes along")
            coming.append(self.require_npc_here(npc_id))
        for npc in coming:
            npc.place = destination.id
        self.visits.append(Visit(place=destination.id))
        if (campaign := self.campaign) is not None and destination.id != campaign.place:
            job = campaign.open_job()
            if job is not None and job.started is None:
                job.started = len(self.visits) - 1
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
        one = self.require(entity_id)
        holders = {self.current.id, *(member.id for member in self.here())}
        location = one.place if isinstance(one, Npc) else one.on if isinstance(one, Item) else None
        if location not in holders:
            raise Refusal(f"{one.name} is not here with the player")
        found = "found" if isinstance(one, Item) else "discovered"
        if one.known:
            raise Refusal(f"the player has already {found} {one.name}")
        one.known = True
        return [
            one.fact("entity_discovered", f"learned of {one.label}", card=f"{one.name} {found}")
        ]

    def move_item(self, item_id: EntityId, to: EntityId) -> list[Fact]:
        item = self.require_item_here(item_id)
        if to != self.player.id and to != self.current.id:
            npc = next((one for one in self.here() if one.id == to and one.alive), None)
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

    def kill(self, one: Goon | Npc) -> list[Fact]:
        """Whatever the dead carried lies loose where they fell, the player's kit included."""
        facts = one.reveal()
        one.alive = False
        dropped = list(self.carried(one.id))
        for item in dropped:
            item.on = self.current.id
        if dropped:
            fell = ", ".join(item.label for item in dropped) + " fell loose here"
            facts.append(Fact(kind="items_dropped", trace=fell))
        card = "You are dead" if one.id == self.player.id else f"{one.name} is dead"
        facts.append(one.fact("actor_killed", f"{one.label} is dead", card=card))
        return facts

    def attach(self, region: Dungeon, start: EntityId, *, known: bool) -> None:
        """No bar runs here: every caller refuses first, so a refused region leaves it alone."""
        anchor_id = self.current.id
        self.places.update(region.places)
        # Copied: the anchor ways appended below must not land in the draft's own lists.
        self.ways.update({key: [*ways] for key, ways in region.ways.items()})
        self.npcs.update(region.npcs)
        self.items.update(region.items)
        self.add_way(anchor_id, start, known=known)
        self.add_way(start, anchor_id, known=known)

    def line(self, one: Goon | Npc | Item) -> str:
        """One card line, its sheet shaped by what kind of entity it names."""
        line = f"- {one.name}[{one.id}]" + (f" — {one.brief}" if one.brief else "")
        if isinstance(one, Goon):
            sheet = "; ".join(f"{label.lower()}: {value}" for label, value in self.sheet_rows(one))
        elif isinstance(one, Npc):
            sheet = f"health: {one.hp} (its Difficulty Score)"
        else:
            sheet = ""
        if isinstance(one, Goon | Npc) and not one.alive:
            line += " (dead)"
        return f"{line}\n  {sheet}" if sheet else line

    def sheet_rows(self, goon: Goon) -> Rows:
        carried = len(list(self.carried(goon.id)))
        return tuple(
            (label, f"{carried}/{goon.inventory}") if label == "Inventory" else (label, value)
            for label, value in goon.rows()
        )

    def exchanges(self) -> tuple[Exchange, ...]:
        return tuple(one for visit in self.visits for one in visit.exchanges)

    def scenes(self) -> tuple[SceneRecord, ...]:
        records: list[SceneRecord] = []
        for visit in self.job_visits():
            place = self.require_place(visit.place)
            records.append(
                SceneRecord(
                    title=place.name, question=place.brief, exchanges=tuple(visit.exchanges)
                )
            )
        return tuple(records)


class TunnelGoonsGame(Game[TunnelGoonsWorld]):
    pass


class TunnelGoonsScenario(Scenario[MapCanon]):
    pass


class TunnelGoonsCharacter(Character[Goon]):
    pass


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
