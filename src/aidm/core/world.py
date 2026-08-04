from collections.abc import Iterator, Mapping
from typing import Literal, Self

from pydantic import Field, model_validator

from .base import PLAYER_ID, EngineId, Entity, EntityId, Frozen, Kind, Mutable, Slug
from .facts import CORE, Fact

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


class EngineRules(Mutable):
    kind: Kind


class BareLocation(EngineRules):
    # The Literal narrowing is the discriminator pattern; every payload subclass repeats it.
    kind: Literal["location"] = "location"  # pyright: ignore[reportIncompatibleVariableOverride]


class Record[R: EngineRules](Mutable):
    entity: Entity
    rules: R

    @model_validator(mode="after")
    def _kind_agrees(self) -> Self:
        if self.rules.kind != self.entity.kind:
            raise ValueError(
                f"{self.entity.id!r} is a {self.entity.kind} with {self.rules.kind} rules"
            )
        return self


def rules_of[R: EngineRules, T: EngineRules](record: Record[R], cls: type[T]) -> T:
    if not isinstance(record.rules, cls):
        raise ValueError(f"{record.entity.id!r} carries no {cls.__name__}")
    return record.rules


class WorldState[R: EngineRules](Mutable):
    records: dict[EntityId, Record[R]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _keys_match_ids(self) -> Self:
        mismatched = sorted(key for key, record in self.records.items() if key != record.entity.id)
        if mismatched:
            raise ValueError(f"entity keys disagree with their ids: {mismatched}")
        return self

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

    def record(self, entity_id: EntityId, kind: Kind | None = None) -> Record[R]:
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


class GameState[R: EngineRules](Mutable):
    save_version: int
    scenario_id: Slug
    character_id: Slug
    scenario: ScenarioMeta
    engine: EngineId
    world: WorldState[R]
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
        """One validation per transaction; `type(self)` revalidates payloads as the union."""
        return type(self).model_validate(self.model_dump(round_trip=True))

    def add(self, entity: Entity, rules: R) -> Fact:
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
        return self


def _move_summary(entity: Entity, destination: Entity) -> str:
    if entity.kind == "actor":
        return f"{entity.name} moved to {destination.name}"
    if destination.id == PLAYER_ID:
        return f"took {entity.name}"
    if destination.kind == "actor":
        return f"gave {entity.name} to {destination.name}"
    return f"left {entity.name} at {destination.name}"
