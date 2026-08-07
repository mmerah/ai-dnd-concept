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
from .effects import TurnEffect
from .facts import CORE, Fact
from .sheet import Sheet

_HOLDERS: Mapping[Kind, tuple[Kind, ...]] = {
    "actor": ("location",),
    "item": ("actor", "location"),
    "location": (),
}


def check_placement(entity: Entity, holder: Entity | None) -> None:
    """One topology rule, read by the committed world and by authored content alike."""
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
    kind: Slug
    title: str
    status: ThreadStatus = "active"
    stage: Slug | None = None
    note: str = ""


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
    effects: tuple[TurnEffect, ...] = ()
    note: str = ""


class Record(Mutable):
    entity: Entity
    rules: Sheet

    @model_validator(mode="after")
    def _kind_agrees(self) -> Self:
        if self.rules.kind != self.entity.kind:
            raise ValueError(
                f"{self.entity.id!r} is a {self.entity.kind} with {self.rules.kind} rules"
            )
        return self


class WorldState(Mutable):
    records: dict[EntityId, Record] = Field(default_factory=dict)
    relations: dict[RelationId, Relation] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _keys_match_ids(self) -> Self:
        mismatched = sorted(key for key, record in self.records.items() if key != record.entity.id)
        if mismatched:
            raise ValueError(f"entity keys disagree with their ids: {mismatched}")
        stale = sorted(key for key, relation in self.relations.items() if key != relation.id)
        if stale:
            raise ValueError(f"relation keys disagree with their ids: {stale}")
        for relation in self.relations.values():
            self._check_relation(relation)
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

    def entities(self, kind: Kind | None = None) -> Iterator[Entity]:
        return (
            record.entity
            for record in self.records.values()
            if kind is None or record.entity.kind == kind
        )

    def all_ids(self) -> set[EntityId]:
        return set(self.records)

    def find(self, entity_id: EntityId) -> Entity | None:
        record = self.records.get(entity_id)
        return None if record is None else record.entity

    def record(self, entity_id: EntityId, kind: Kind | None = None) -> Record:
        record = self.records.get(entity_id)
        if record is None:
            raise ValueError(f"unknown entity id {entity_id!r}")
        if kind is not None and record.entity.kind != kind:
            raise ValueError(f"used {entity_id!r} as {kind}, but it is a {record.entity.kind}")
        return record

    def require(self, entity_id: EntityId) -> Entity:
        return self.record(entity_id).entity

    def require_kind(self, entity_id: EntityId, kind: Kind) -> Entity:
        return self.record(entity_id, kind).entity

    def children(self, entity_id: EntityId, kind: Kind | None = None) -> tuple[Entity, ...]:
        return tuple(entity for entity in self.entities(kind) if entity.parent_id == entity_id)

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
    threads: dict[Slug, Thread] = Field(default_factory=dict)
    hooks: tuple[Hook, ...] = ()
    # A tuple, not a set: a save's bytes are a golden fixture, and set ordering is not stable.
    fired_hooks: tuple[Slug, ...] = ()
    pending_notes: tuple[str, ...] = ()
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

    def add(self, entity: Entity, rules: Sheet) -> Fact:
        """Copy into the fact, so a later move in the same turn cannot rewrite the record."""
        if self.world.find(entity.id) is not None:
            raise ValueError(f"entity id {entity.id!r} already exists")
        self.world.records[entity.id] = Record(entity=entity, rules=rules)
        summary = f"new {entity.kind}: {entity.name}"
        return Fact(
            source=CORE,
            kind="entity_created",
            trace=summary,
            narrator=summary,
            data={"entity_id": entity.id, "kind": entity.kind, "name": entity.name},
        )

    def reveal(self, entity: Entity) -> list[Fact]:
        if entity.known:
            return []
        entity.known = True
        summary = f"learned of {entity.name}"
        return [
            Fact(
                source=CORE,
                kind="entity_discovered",
                trace=summary,
                narrator=summary,
                data={"entity_id": entity.id, "name": entity.name},
            )
        ]

    def move(self, entity: Entity, destination: Entity) -> Fact:
        entity.parent_id = destination.id
        summary = _move_summary(entity, destination)
        return Fact(
            source=CORE,
            kind="entity_moved",
            trace=summary,
            narrator=summary,
            data={
                "entity_id": entity.id,
                "entity_name": entity.name,
                "to_id": destination.id,
                "to_name": destination.name,
                "to_kind": destination.kind,
            },
        )

    @model_validator(mode="after")
    def _consistent_world(self) -> Self:
        if not self.player.known:
            raise ValueError("the player entity must be known")
        for entity in self.world.entities():
            # `find`, not `require`: a dangling id is a topology fault, not a lookup failure.
            holder = None if entity.parent_id is None else self.world.find(entity.parent_id)
            check_placement(entity, holder)
        mismatched = sorted(key for key, thread in self.threads.items() if key != thread.id)
        if mismatched:
            raise ValueError(f"thread keys disagree with their ids: {mismatched}")
        by_id = {hook.id for hook in self.hooks}
        if len(by_id) != len(self.hooks):
            raise ValueError("two hooks share an id, so one would never be told it had fired")
        if unknown := sorted(set(self.fired_hooks) - by_id):
            raise ValueError(f"fired hooks name no authored hook: {unknown}")
        if len(set(self.fired_hooks)) != len(self.fired_hooks):
            raise ValueError(f"a hook fired twice: {sorted(self.fired_hooks)}")
        return self


def sheet_of(state: GameState, entity_id: EntityId) -> Sheet:
    return state.world.record(entity_id).rules


def player_sheet(state: GameState) -> Sheet:
    return sheet_of(state, PLAYER_ID)


def _move_summary(entity: Entity, destination: Entity) -> str:
    if entity.kind == "actor":
        return f"{entity.name} moved to {destination.name}"
    if destination.id == PLAYER_ID:
        return f"took {entity.name}"
    if destination.kind == "actor":
        return f"gave {entity.name} to {destination.name}"
    return f"left {entity.name} at {destination.name}"
