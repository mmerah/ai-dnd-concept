from collections.abc import Iterable, Iterator, Sequence
from functools import partial
from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Mutable, require_unique, slug
from aidm.core.facts import DiceEvent, Fact, cards
from aidm.core.model import Character, Game, Scenario
from aidm.core.play import Exchange, SpokenLine
from aidm.core.views import Rows
from aidm.engines.core import PLAYER_ID, Counter, pool

Ability = Literal["brute", "skulker", "erudite"]
ABILITIES: tuple[Ability, ...] = ("brute", "skulker", "erudite")
Boost = Literal["health", "inventory"]
HP_START = 10
INVENTORY_START = 8
ABILITY_POINTS = 3
STARTING_ITEMS = 3


class Goon(Mutable):
    """The played character: the only one with abilities, and the only one who rolls."""

    id: CheckedEntityId
    name: str
    brief: str
    known: bool = False
    place: CheckedEntityId
    brute: int = Field(default=0, ge=0)
    skulker: int = Field(default=0, ge=0)
    erudite: int = Field(default=0, ge=0)
    hp: Counter = Field(default_factory=partial(Counter, current=HP_START, maximum=HP_START))
    inventory: int = Field(default=INVENTORY_START, ge=0)
    level: int = Field(default=1, ge=1)
    alive: bool = True

    def ability(self, name: Ability) -> int:
        match name:
            case "brute":
                return self.brute
            case "skulker":
                return self.skulker
            case "erudite":
                return self.erudite

    def rows(self) -> Rows:
        return (
            ("Brute", str(self.brute)),
            ("Skulker", str(self.skulker)),
            ("Erudite", str(self.erudite)),
            ("Health", pool(self.hp)),
            ("Inventory", str(self.inventory)),
            ("Level", str(self.level)),
        )


class Npc(Mutable):
    """Every non-player character, friend or foe: the SRD gives them one shape."""

    id: CheckedEntityId
    name: str
    brief: str
    known: bool = False
    place: CheckedEntityId
    # SRD: an NPC's Difficulty Score is also its Health Points, so one counter serves both.
    hp: Counter
    alive: bool = True


class Item(Mutable):
    id: CheckedEntityId
    name: str
    brief: str
    known: bool = False
    on: CheckedEntityId


class Place(Mutable):
    id: CheckedEntityId
    name: str
    brief: str
    known: bool = False
    description: str = Field(min_length=1)


class Way(Mutable):
    """One directed passage from the place under which it is filed."""

    to: CheckedEntityId
    known: bool = False
    locked: bool = False


class Visit(Mutable):
    place: CheckedEntityId
    exchanges: list[Exchange] = Field(default_factory=list)


# A plain alias, not `type`: it names the four kinds a validator or a card line matches on.
Entity = Goon | Npc | Item | Place


class Dungeon(Mutable):
    """The map and everything in it; the holder matrix is in the types."""

    places: dict[EntityId, Place] = Field(default_factory=dict)
    ways: dict[EntityId, tuple[Way, ...]] = Field(default_factory=dict)
    npcs: dict[EntityId, Npc] = Field(default_factory=dict)
    items: dict[EntityId, Item] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        _check_filing(self.places)
        _check_filing(self.npcs)
        _check_filing(self.items)
        require_unique("ids across places, npcs and items", (*self.places, *self.npcs, *self.items))
        for one in self.npcs.values():
            if one.place not in self.places:
                raise ValueError(f"{one.name} is in no place: {one.place!r}")
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

    def entity(self, entity_id: EntityId) -> Entity | None:
        return self.places.get(entity_id) or self.npcs.get(entity_id) or self.items.get(entity_id)

    def require(self, entity_id: EntityId) -> Entity:
        one = self.entity(entity_id)
        if one is None:
            raise ValueError(f"unknown id {entity_id!r}. Use only ids you were shown.")
        return one

    def require_place(self, entity_id: EntityId) -> Place:
        one = self.require(entity_id)
        if not isinstance(one, Place):
            raise ValueError(f"{entity_id!r} is not a place")
        return one

    def way(self, from_id: EntityId, to_id: EntityId) -> Way | None:
        return next((one for one in self.ways.get(from_id, ()) if one.to == to_id), None)

    def at(self, place_id: EntityId) -> Iterator[Npc]:
        return (one for one in self.npcs.values() if one.place == place_id)

    def carried(self, holder_id: EntityId) -> Iterator[Item]:
        """A place holds what lies loose in it, the same way an npc holds what it carries."""
        return (one for one in self.items.values() if one.on == holder_id)


class MapCanon(Dungeon):
    """An authored map before the played character stands at its start."""

    start: CheckedEntityId
    source: str = ""

    @model_validator(mode="after")
    def _startable(self) -> Self:
        if not self.require_place(self.start).known:
            raise ValueError("the starting place must be known to the player")
        return self


class TunnelWorld(Dungeon):
    player: Goon
    visits: list[Visit] = Field(min_length=1)
    source: str = ""

    @model_validator(mode="after")
    def _playable(self) -> Self:
        if not self.player.known:
            raise ValueError("the player is unknown to themselves")
        for visit in self.visits:
            _ = self.require_place(visit.place)
        if self.visits[-1].place != self.player.place:
            raise ValueError("the last visit is not where the player stands")
        return self

    @property
    def current(self) -> Place:
        return self.places[self.player.place]

    @property
    def visit(self) -> Visit:
        return self.visits[-1]

    def entity(self, entity_id: EntityId) -> Entity | None:
        return self.player if entity_id == self.player.id else super().entity(entity_id)

    def here(self) -> Iterator[Goon | Npc]:
        yield self.player
        yield from self.at(self.current.id)

    def require_npc_here(self, entity_id: EntityId) -> Npc:
        npc = self.npcs.get(entity_id)
        if npc is None:
            raise ValueError(f"unknown id {entity_id!r}. Use only ids you were shown.")
        if not npc.alive:
            raise ValueError(f"{npc.name} is dead; they take no further part.")
        if npc.place != self.player.place:
            raise ValueError(f"{npc.name} is not here with the player")
        return npc

    def require_item_here(self, item_id: EntityId) -> Item:
        item = self.require(item_id)
        if not isinstance(item, Item):
            raise ValueError(f"{item_id!r} is not an item")
        holders = {self.current.id, *(one.id for one in self.here())}
        if item.on not in holders:
            raise ValueError(f"{item.name} is not here with the player")
        return item

    def label(self, one: Entity) -> str:
        if one.id == self.player.id:
            return f"the player {one.name}[{one.id}]"
        return f"{one.name}[{one.id}]"

    def reveal(self, one: Entity) -> list[Fact]:
        if one.known:
            return []
        one.known = True
        return [entity_fact(one, "entity_discovered", f"learned of {self.label(one)}")]

    def exchanges(self) -> tuple[Exchange, ...]:
        return tuple(
            one
            if one.where
            else one.model_copy(update={"where": self.require_place(visit.place).name})
            for visit in self.visits
            for one in visit.exchanges
        )


class TunnelGoonsState(Mutable):
    engine: Literal["tunnelgoons"] = "tunnelgoons"
    world: TunnelWorld


class TunnelGoonsScenario(Mutable):
    engine: Literal["tunnelgoons"] = "tunnelgoons"
    world: MapCanon


class TunnelGoonsCharacter(Mutable):
    engine: Literal["tunnelgoons"] = "tunnelgoons"
    brute: int = Field(ge=0)
    skulker: int = Field(ge=0)
    erudite: int = Field(ge=0)
    items: tuple[str, ...] = Field(min_length=STARTING_ITEMS, max_length=STARTING_ITEMS)

    @model_validator(mode="after")
    def _shares_ability_points(self) -> Self:
        if self.brute + self.skulker + self.erudite != ABILITY_POINTS:
            raise ValueError(f"the three abilities share exactly {ABILITY_POINTS} points")
        return self


class TunnelGoonsGame(Game[TunnelGoonsState]):
    pass


class TunnelGoonsScenarioFile(Scenario[TunnelGoonsScenario]):
    pass


class TunnelGoonsCharacterFile(Character[TunnelGoonsCharacter]):
    pass


def entity_fact(
    one: Entity,
    kind: str,
    trace: str,
    *,
    narrate: bool = True,
    card: str = "",
    dice: tuple[DiceEvent, ...] = (),
) -> Fact:
    """An entity the player has not learned of narrates nothing, so no unknown name leaks."""
    return Fact(
        kind=kind, trace=trace, told=narrate and one.known, entity_id=one.id, card=card, dice=dice
    )


def known(state: TunnelGoonsGame, entity_id: EntityId) -> bool | None:
    one = state.payload.world.entity(entity_id)
    return None if one is None else one.known


def record(
    state: TunnelGoonsGame, prompt: str, lines: tuple[SpokenLine, ...], facts: Sequence[Fact]
) -> tuple[str, ...]:
    world = state.payload.world
    world.visit.exchanges.append(
        Exchange(
            prompt=prompt,
            lines=lines,
            facts=cards(facts),
            decision="" if state.pending is None else state.pending.prompt,
        )
    )
    return ()


def history(state: TunnelGoonsGame) -> tuple[Exchange, ...]:
    return state.payload.world.exchanges()


def player_over(state: TunnelGoonsGame) -> str | None:
    return "You died." if not state.payload.world.player.alive else None


def player_goon(character: TunnelGoonsCharacterFile, place: EntityId) -> Goon:
    """The played character as the world holds them; `new_game` and `preview_character` share it."""
    payload = character.payload
    return Goon(
        id=PLAYER_ID,
        name=character.name,
        brief=character.brief,
        known=True,
        place=place,
        brute=payload.brute,
        skulker=payload.skulker,
        erudite=payload.erudite,
    )


def starting_items(character: TunnelGoonsCharacterFile, taken: Iterable[str]) -> tuple[Item, ...]:
    made = list(taken)
    items: list[Item] = []
    for name in character.payload.items:
        item_id = EntityId(slug(name, made))
        made.append(item_id)
        items.append(Item(id=item_id, name=name, brief="", known=True, on=PLAYER_ID))
    return tuple(items)


def frontier(world: Dungeon) -> int:
    """Count distinct unknown places reachable through ways out of known places."""
    return len(
        {
            way.to
            for from_id, ways in world.ways.items()
            if world.require_place(from_id).known
            for way in ways
            if not world.require_place(way.to).known
        }
    )


def walk(
    ways: dict[EntityId, tuple[Way, ...]], start: EntityId, places: dict[EntityId, Place]
) -> set[EntityId]:
    reached = {start}
    pending = [start]
    while pending:
        current = pending.pop()
        for way in ways.get(current, ()):
            if way.to not in reached and way.to in places:
                reached.add(way.to)
                pending.append(way.to)
    return reached


def has_shortcut(ways: dict[EntityId, tuple[Way, ...]], places: dict[EntityId, Place]) -> bool:
    """A shortcut is an edge whose destination remains reachable after that edge is removed."""
    return any(
        direct.to
        in walk({**ways, start: tuple(w for w in leaving if w is not direct)}, start, places)
        for start, leaving in ways.items()
        for direct in leaving
    )


def _check_filing[T: Npc | Item | Place](pool: dict[EntityId, T]) -> None:
    for key, one in pool.items():
        if key != one.id:
            raise ValueError(f"entity {one.id!r} is filed under {key!r}")
