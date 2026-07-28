"""The character sheet, the scenario identity vs. live world, and the state that ties them."""

from collections.abc import Sequence
from typing import Self

from pydantic import Field, model_validator

from ...content import ContentRef, PackStamp
from ...utils.models import EMPTY_FROZEN_MAP, Attributes, Frozen, updated
from .base import PLAYER_ID, SAVE_VERSION, EntityId, slug
from .entities import ActorEntity, Entity, ItemEntity, LocationEntity
from .progression import Advancement, Decisions, Origin
from .stats import StatBlock


class StartingItem(Frozen):
    """An item the character starts with, promoted to a canon item at composition."""

    name: str
    brief: str
    ref: ContentRef | None = None


class CharacterSheet(Frozen):
    """The on-disk character definition. The entity it seeds, not the sheet, owns values a level-up
    evolves — so there is no starting hit point total here: `origin`'s class supplies the hit die,
    and `engine/progression.py` supplies the formula.

    `starting_attributes` is the base roll, before a race's bonuses; `decisions` are the level-1
    picks, keyed by `ProgressionChoice.id`. Without either, character creation could not produce a
    legal 5e character."""

    name: str
    brief: str
    origin: Origin
    starting_attributes: Attributes = Attributes()
    decisions: Decisions = EMPTY_FROZEN_MAP
    starting_items: tuple[StartingItem, ...] = ()


class ScenarioMeta(Frozen):
    """Static scenario identity. Lives inside GameState and is never edited during play."""

    title: str
    premise: str


class WorldState(Frozen):
    """The live canon the reducer edits — everything discover/Maintainer/Creator touch.

    Keyed by id so uniqueness is a guarantee, not an assumption; `Entity.id` is kept because an
    entity travels standalone (through `EntityCreated`, `Turn.created`, `create()`'s return)."""

    entities: dict[EntityId, Entity] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _keys_match_ids(self) -> Self:
        """The id is stored twice after a JSON round-trip; a mismatch would make lookups lie."""
        if wrong := [k for k, e in self.entities.items() if k != e.id]:
            raise ValueError(f"entity keys disagree with their ids: {wrong}")
        return self

    def require(self, entity_id: EntityId) -> Entity:
        """Fail fast: an id nothing answers for is a broken plan."""
        entity = self.entities.get(entity_id)
        if entity is None:
            raise ValueError(f"unknown entity id {entity_id!r}")
        return entity

    def require_kind[T: Entity](self, entity_id: EntityId, expected: type[T]) -> T:
        """`expected` is a concrete class: `Entity` is a union, which `isinstance` cannot take."""
        entity = self.require(entity_id)
        if not isinstance(entity, expected):
            raise ValueError(
                f"used {entity_id!r} as {expected.__name__}, but it is a {entity.kind}"
            )
        return entity

    def replacing(self, entity: Entity) -> Self:
        """The only edit shape the reducer needs, so nothing copies the entity map by hand."""
        return updated(self, entities={**self.entities, entity.id: entity})

    def adding(self, entity: Entity) -> Self:
        """A brand new entity. A duplicate id is a broken invariant, never an update: a name
        collision is a judgement call screened in `engine/growth.py`, an id collision is not."""
        if entity.id in self.entities:
            raise ValueError(f"entity id {entity.id!r} already exists")
        return self.replacing(entity)

    def location_of(self, entity: Entity) -> EntityId | None:
        """Where an entity is, or `None` for a location, which is not anywhere else. A carried item
        is where its holder stands, so containment never hides something from its own room."""
        match entity:
            case LocationEntity():
                return None
            case ActorEntity():
                return entity.location_id
            case ItemEntity():
                held_by = self.container_of(entity)
                return held_by.id if isinstance(held_by, LocationEntity) else held_by.location_id

    def container_of(self, item: ItemEntity) -> ActorEntity | LocationEntity:
        """The actor carrying it or the location it lies at — `GameState` guarantees one of the
        two, and this raise is what guarantees it."""
        container = self.entities.get(item.container_id)
        if not isinstance(container, ActorEntity | LocationEntity):
            raise ValueError(f"item {item.id!r} is in {item.container_id!r}, which holds nothing")
        return container

    def carried_by(self, actor_id: EntityId) -> list[ItemEntity]:
        """What an actor carries. Order is entity-map order; a view that shows it should sort."""
        return [
            e
            for e in self.entities.values()
            if isinstance(e, ItemEntity) and e.container_id == actor_id
        ]


class ScenarioDef(Frozen):
    """The on-disk scenario file: static identity, starting canon, and where a character begins.
    Entities stay a JSON array — a list is the natural authoring shape."""

    meta: ScenarioMeta
    starting_location_id: EntityId
    entities: list[Entity] = Field(default_factory=list)

    @model_validator(mode="after")
    def _valid_scenario(self) -> Self:
        """Checked here so a malformed scenario fails at its own boundary, not mid-turn."""
        ids = [e.id for e in self.entities]
        if duplicates := sorted({i for i in ids if ids.count(i) > 1}):
            raise ValueError(f"scenario has duplicate entity ids: {duplicates}")
        # A scenario must place any character, not just one it names; the sheet supplies the player.
        if PLAYER_ID in ids:
            raise ValueError(f"an entity claims the reserved player id {PLAYER_ID!r}")
        start = next((e for e in self.entities if e.id == self.starting_location_id), None)
        if start is None or start.kind != "location":
            raise ValueError(
                f"starting_location_id {self.starting_location_id!r} is not a location here"
            )
        return self


class Exchange(Frozen):
    prompt: str
    narration: str


class GameState(Frozen):
    version: int = SAVE_VERSION
    scenario: ScenarioMeta
    world: WorldState
    # The versions the entities' stats were snapshotted from; `store.load` refuses a mismatch.
    packs: list[PackStamp] = Field(default_factory=list)
    history: list[Exchange] = Field(default_factory=list)
    turn: int = 0

    @property
    def player(self) -> ActorEntity:
        player = self.world.entities.get(PLAYER_ID)
        if not isinstance(player, ActorEntity):
            raise ValueError(f"the reserved id {PLAYER_ID!r} does not name an actor")
        return player

    @model_validator(mode="after")
    def _consistent_world(self) -> Self:
        """Positions must be real, so lookups never lie: every actor stands in a location, and
        every item is in something that can hold it."""
        entities = self.world.entities

        # Unrevealed canon is offered as a `discover` target; the player must never be one.
        if not self.player.known:
            raise ValueError("the player entity must be known")
        # Progression is the player's alone, so `LeveledUp` needs no target id to be unambiguous.
        if levelled := sorted(
            e.id
            for e in entities.values()
            if isinstance(e, ActorEntity) and e.progression is not None and e.id != PLAYER_ID
        ):
            raise ValueError(f"only the player may have progression: {levelled}")

        for actor in (e for e in entities.values() if isinstance(e, ActorEntity)):
            if not isinstance(entities.get(actor.location_id), LocationEntity):
                raise ValueError(f"actor {actor.id!r} is not in a valid location")
        for item in (e for e in entities.values() if isinstance(e, ItemEntity)):
            self.world.container_of(item)  # its raise is the invariant: an actor xor a location
        return self

    @classmethod
    def from_scenario(
        cls,
        scenario: ScenarioDef,
        character: CharacterSheet,
        packs: Sequence[PackStamp],
        start: Advancement,
    ) -> Self:
        """A sheet placed at the scenario's start, over its canon. Starting items become canon items
        contained by the player, so what they carry holds real ids, not free text. The pack stamps
        and the level-1 `Advancement` are handed in because deriving either means reading a pack,
        which `domain/` does not do."""
        entities = {entity.id: entity for entity in scenario.entities}
        for item in character.starting_items:
            entity = ItemEntity(
                id=slug(item.name, entities.keys()),
                name=item.name,
                brief=item.brief,
                ref=item.ref,
                known=True,
                container_id=PLAYER_ID,  # inserted below; validation runs on the finished state
            )
            entities[entity.id] = entity
        entities[PLAYER_ID] = ActorEntity(
            id=PLAYER_ID,
            name=character.name,
            brief=character.brief,
            known=True,
            location_id=scenario.starting_location_id,
            stats=StatBlock(attributes=start.attributes, max_hp=start.hp_gain, hp=start.hp_gain),
            progression=start.progression,
        )
        return cls(scenario=scenario.meta, world=WorldState(entities=entities), packs=list(packs))
