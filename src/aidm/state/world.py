from collections.abc import Iterator, Mapping
from typing import Self

from pydantic import Field, JsonValue, model_validator

from .base import (
    PLAYER_ID,
    EngineId,
    Entity,
    EntityId,
    Frozen,
    Kind,
    Mutable,
    RelationId,
    Slug,
    ThreadStatus,
)
from .effects import WorldEffect
from .facts import Fact, entity_fact

_HOLDERS: Mapping[Kind, tuple[Kind, ...]] = {
    "actor": ("location",),
    "item": ("actor", "location"),
    "location": (),
}


def check_placement(entity: Entity, holder: Entity | None) -> None:
    allowed = _HOLDERS[entity.kind]
    if not allowed:
        if entity.parent_id is not None:
            raise ValueError(f"{entity.kind} {entity.id!r} cannot be inside anything")
        return
    if holder is None:
        raise ValueError(f"{entity.kind} {entity.id!r} is not in a valid {' or '.join(allowed)}")
    if holder.kind not in allowed:
        raise ValueError(f"{entity.kind} {entity.id!r} is in a {holder.kind}, which cannot hold it")


CONNECTED: Slug = "connected"
PARTY_MEMBER: Slug = "party-member"
LOCKED_TAG: Slug = "locked"


class Relation(Mutable):
    """A lasting tie that is not containment: `parent_id` still owns the holder topology."""

    kind: Slug
    source: EntityId
    target: EntityId
    directed: bool = True
    known: bool = False
    tags: list[Slug] = Field(default_factory=list)

    @property
    def id(self) -> RelationId:
        """An undirected tie sorts its endpoints, so `a-b` and `b-a` are one relation, not two."""
        ends = (self.source, self.target)
        first, second = ends if self.directed else tuple(sorted(ends))
        return RelationId(f"{self.kind}/{first}/{second}")

    def joins(self, source: EntityId, target: EntityId) -> bool:
        if (self.source, self.target) == (source, target):
            return True
        return not self.directed and (self.source, self.target) == (target, source)

    def touches(self, entity_id: EntityId) -> bool:
        return entity_id in (self.source, self.target)

    def far_end(self, entity_id: EntityId) -> EntityId:
        return self.target if entity_id == self.source else self.source


class Thread(Mutable):
    """A storyline the scenario tracks: a quest, an investigation, or a countdown."""

    id: Slug
    title: str
    status: ThreadStatus = "active"
    stage: Slug | None = None
    note: str = ""


class Memory(Mutable):
    """A durable fact the world or one of its people holds, outliving the history window."""

    id: Slug
    owner: EntityId | None = None
    text: str = Field(min_length=1, max_length=300)


class HookMatch(Frozen):
    """A fact this hook waits for: its kind, and the data fields that must equal these."""

    kind: str
    data: dict[str, JsonValue] = Field(default_factory=dict)

    def matches(self, fact: Fact) -> bool:
        return fact.kind == self.kind and all(
            fact.data.get(key) == value for key, value in self.data.items()
        )


class Hook(Frozen):
    """Authored consequence: a committed fact fires it, so a scenario advances without engine
    code. Its `note` steers the Director on the following turn."""

    id: Slug
    match: HookMatch
    effects: tuple[WorldEffect, ...] = ()
    note: str = ""


class WorldState(Mutable):
    """The whole persistent fiction; `GameState` holds the played game around it."""

    entities: dict[EntityId, Entity] = Field(default_factory=dict)
    relations: dict[RelationId, Relation] = Field(default_factory=dict)
    threads: dict[Slug, Thread] = Field(default_factory=dict)
    memories: dict[Slug, Memory] = Field(default_factory=dict)
    hooks: tuple[Hook, ...] = ()
    # A tuple, not a set: a save's bytes are a golden fixture, and set ordering is not stable.
    fired_hooks: tuple[Slug, ...] = ()
    pending_notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _consistent_fiction(self) -> Self:
        keyed = (
            ("entity", self.entities),
            ("relation", self.relations),
            ("thread", self.threads),
            ("memory", self.memories),
        )
        mismatched = sorted(
            f"{what} {key!r}"
            for what, entries in keyed
            for key, entry in entries.items()
            if key != entry.id
        )
        if mismatched:
            raise ValueError(f"keys disagree with their ids: {mismatched}")
        for entity in self.entities.values():
            # `find`, not `require`: a dangling id is a topology fault, not a lookup failure.
            holder = None if entity.parent_id is None else self.find(entity.parent_id)
            check_placement(entity, holder)
        for relation in self.relations.values():
            self._check_relation(relation)
        for memory in self.memories.values():
            if memory.owner is not None and memory.owner not in self.entities:
                raise ValueError(f"memory {memory.id!r} is held by unknown entity {memory.owner!r}")
        authored = {hook.id for hook in self.hooks}
        if len(authored) != len(self.hooks):
            raise ValueError("two hooks share an id, so one would never be told it had fired")
        if unknown := sorted(set(self.fired_hooks) - authored):
            raise ValueError(f"fired hooks name no authored hook: {unknown}")
        if len(set(self.fired_hooks)) != len(self.fired_hooks):
            raise ValueError(f"a hook fired twice: {sorted(self.fired_hooks)}")
        return self

    def _check_relation(self, relation: Relation) -> None:
        """The two kinds core interprets are checked here, so a typo'd slug fails at load rather
        than silently disabling movement gating or party travel."""
        ends = [self.require(relation.source), self.require(relation.target)]
        if relation.known and not all(end.known for end in ends):
            raise ValueError(
                f"known relation {relation.id!r} names an entity the player has not met"
            )
        if relation.kind == CONNECTED and any(end.kind != "location" for end in ends):
            raise ValueError(f"{CONNECTED!r} joins two locations, and {relation.id!r} does not")
        if relation.kind == PARTY_MEMBER and (
            ends[0].kind != "actor" or relation.target != PLAYER_ID
        ):
            raise ValueError(
                f"{PARTY_MEMBER!r} puts an actor in the player's party, unlike {relation.id!r}"
            )

    def connections(self, location_id: EntityId) -> tuple[Relation, ...]:
        return tuple(
            relation
            for relation in self.relations.values()
            if relation.kind == CONNECTED and relation.touches(location_id)
        )

    def party(self) -> tuple[EntityId, ...]:
        return tuple(
            relation.source for relation in self.relations.values() if relation.kind == PARTY_MEMBER
        )

    def relation(self, kind: Slug, source: EntityId, target: EntityId) -> Relation | None:
        return next(
            (
                relation
                for relation in self.relations.values()
                if relation.kind == kind and relation.joins(source, target)
            ),
            None,
        )

    def of_kind(self, kind: Kind) -> Iterator[Entity]:
        return (entity for entity in self.entities.values() if entity.kind == kind)

    def all_ids(self) -> set[EntityId]:
        return set(self.entities)

    def find(self, entity_id: EntityId) -> Entity | None:
        return self.entities.get(entity_id)

    def require(self, entity_id: EntityId) -> Entity:
        entity = self.entities.get(entity_id)
        if entity is None:
            raise ValueError(f"unknown entity id {entity_id!r}")
        return entity

    def require_kind(self, entity_id: EntityId, kind: Kind) -> Entity:
        entity = self.require(entity_id)
        if entity.kind != kind:
            raise ValueError(f"used {entity_id!r} as {kind}, but it is a {entity.kind}")
        return entity

    def children(self, entity_id: EntityId, kind: Kind | None = None) -> tuple[Entity, ...]:
        held = self.entities.values() if kind is None else self.of_kind(kind)
        return tuple(entity for entity in held if entity.parent_id == entity_id)

    def location_of(self, entity: Entity) -> EntityId | None:
        """Walk holders up to the enclosing place; a location is inside none, so it has none."""
        current = entity
        while current.parent_id is not None:
            current = self.require(current.parent_id)
        return None if current.id == entity.id else current.id


class Exchange(Frozen):
    prompt: str
    narration: str


class ScenarioMeta(Frozen):
    title: str
    premise: str


class GameState(Mutable):
    save_version: int
    scenario_id: Slug
    character_id: Slug
    scenario: ScenarioMeta
    engine: EngineId
    world: WorldState
    # Opaque to core: the engine that wrote it is the only reader and the only validator.
    mechanics: JsonValue = None
    history: tuple[Exchange, ...] = ()
    turn: int = Field(default=0, ge=0)

    @property
    def player(self) -> Entity:
        return self.world.require_kind(PLAYER_ID, "actor")

    @property
    def player_location(self) -> EntityId:
        location = self.player.parent_id
        if location is None:
            raise ValueError("the player is not in a location")
        return location

    def is_here(self, entity: Entity) -> bool:
        return self.world.location_of(entity) == self.player_location

    def draft(self) -> Self:
        """A working copy a resolution mutates; a failed turn never replaces the committed state."""
        return self.model_copy(deep=True)

    def committed(self) -> Self:
        """One validation per transaction, over the whole copy rather than per field change."""
        return type(self).model_validate(self.model_dump(round_trip=True))

    def add(self, entity: Entity) -> Fact:
        """Copy into the fact, so a later move in the same turn cannot rewrite the entry."""
        if self.world.find(entity.id) is not None:
            raise ValueError(f"entity id {entity.id!r} already exists")
        self.world.entities[entity.id] = entity
        summary = f"new {entity.kind}: {entity.name}"
        return entity_fact(
            entity, "entity_created", summary, {"kind": entity.kind, "name": entity.name}
        )

    def reveal(self, entity: Entity) -> list[Fact]:
        if entity.known:
            return []
        entity.known = True
        summary = f"learned of {entity.name}"
        return [entity_fact(entity, "entity_discovered", summary, {"name": entity.name})]

    def move(self, entity: Entity, destination: Entity) -> Fact:
        entity.parent_id = destination.id
        return entity_fact(
            entity,
            "entity_moved",
            _move_summary(entity, destination),
            {
                "entity_name": entity.name,
                "to_id": destination.id,
                "to_name": destination.name,
                "to_kind": destination.kind,
            },
        )

    @model_validator(mode="after")
    def _the_player_is_playable(self) -> Self:
        if not self.player.known:
            raise ValueError("the player entity must be known")
        return self


def _move_summary(entity: Entity, destination: Entity) -> str:
    if entity.kind == "actor":
        return f"{entity.name} moved to {destination.name}"
    if destination.id == PLAYER_ID:
        return f"took {entity.name}"
    if destination.kind == "actor":
        return f"gave {entity.name} to {destination.name}"
    return f"left {entity.name} at {destination.name}"
