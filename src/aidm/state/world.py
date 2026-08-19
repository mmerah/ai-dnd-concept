from collections.abc import Iterator, Mapping
from typing import Self

from pydantic import Field, JsonValue, PrivateAttr, model_validator

from .base import (
    PLAYER_ID,
    Counter,
    EngineId,
    Entity,
    EntityId,
    Frozen,
    Kind,
    Mutable,
    Slug,
    ThreadStatus,
    require_unique,
)
from .facts import Fact, entity_fact
from .history import Exchange

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


class Thread(Mutable):
    """A storyline the scenario tracks: a quest, an investigation, or a countdown."""

    id: Slug
    title: str
    status: ThreadStatus = "active"
    stage: Slug | None = None
    note: str = ""
    clock: Counter | None = None

    @model_validator(mode="after")
    def _a_clock_fills(self) -> Self:
        if self.clock is not None and self.clock.maximum is None:
            raise ValueError(f"thread {self.id!r} has a clock with no maximum to fill")
        return self


class AdvanceThread(Frozen):
    thread_id: Slug = Field(description="Exact id of one thread in ACTIVE THREADS.")
    status: ThreadStatus | None = Field(
        default=None, description="Where the thread now stands, or null to leave it as it is."
    )
    stage: Slug | None = Field(
        default=None,
        description="Stable slug for the point it has reached, or null to leave it as it is.",
    )
    tick: int = Field(
        default=0,
        description="How many segments this fills on the thread's clock, when it has one.",
    )

    @model_validator(mode="after")
    def _moves_something(self) -> Self:
        if self.tick < 0:
            raise ValueError("a tick fills a clock; it never runs one backwards")
        if self.status is None and self.stage is None and not self.tick:
            raise ValueError("advance-thread moves a thread's status, its stage, or its clock")
        return self


class Memory(Frozen):
    """A durable fact the world or one of its people holds, outliving the history window."""

    owner: EntityId | None = None
    text: str = Field(min_length=1, max_length=300)


class Hook(Frozen):
    """Authored consequence: the player learning of an entity fires it once, so a scenario
    advances without engine code. Its `note` steers the Director on the following turn."""

    id: Slug
    on_discover: EntityId
    note: str = ""
    reveals: tuple[EntityId, ...] = ()
    advance_thread: AdvanceThread | None = Field(
        default=None,
        description="Move a storyline the scenario is tracking: where it stands now, or "
        "that it is over.",
    )


class WorldState(Mutable):
    """The whole persistent fiction; `GameState` holds the played game around it."""

    entities: list[Entity] = Field(default_factory=list)
    threads: list[Thread] = Field(default_factory=list)
    memories: list[Memory] = Field(default_factory=list)
    hooks: list[Hook] = Field(default_factory=list)
    party: list[EntityId] = Field(default_factory=list)
    # A tuple, not a set: a save's bytes are a golden fixture, and set ordering is not stable.
    fired_hooks: tuple[Slug, ...] = ()
    pending_notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _consistent_fiction(self) -> Self:
        require_unique("entity ids", (entity.id for entity in self.entities))
        require_unique("thread ids", (thread.id for thread in self.threads))
        require_unique("hook ids", (hook.id for hook in self.hooks))
        for entity in self.entities:
            # `find`, not `require`: a dangling id is a topology fault, not a lookup failure.
            holder = None if entity.parent_id is None else self.find(entity.parent_id)
            check_placement(entity, holder)
            self._check_exits(entity)
        self._check_party()
        for memory in self.memories:
            if memory.owner is not None and self.find(memory.owner) is None:
                raise ValueError(f"a memory is held by unknown entity {memory.owner!r}")
        authored = {hook.id for hook in self.hooks}
        if unknown := sorted(set(self.fired_hooks) - authored):
            raise ValueError(f"fired hooks name no authored hook: {unknown}")
        require_unique("fired hooks", self.fired_hooks)
        return self

    def _check_exits(self, entity: Entity) -> None:
        """A way the player knows must lead somewhere they may be told about, or the scene would
        name a place they have not learned of."""
        if entity.exits and entity.kind != "location":
            raise ValueError(f"{entity.kind} {entity.id!r} cannot have exits")
        for way in entity.exits:
            far = self.require_kind(way.to, "location")
            if way.known and not (entity.known and far.known):
                raise ValueError(
                    f"the known way from {entity.id!r} to {way.to!r} names a place the player "
                    "has not met"
                )

    def _check_party(self) -> None:
        require_unique("party members", self.party)
        if PLAYER_ID in self.party:
            raise ValueError("the player cannot travel with themselves")
        for member_id in self.party:
            member = self.require_kind(member_id, "actor")
            if not member.known:
                raise ValueError(f"{member_id!r} travels with the player without being met")

    def of_kind(self, kind: Kind) -> Iterator[Entity]:
        return (entity for entity in self.entities if entity.kind == kind)

    def all_ids(self) -> set[EntityId]:
        return {entity.id for entity in self.entities}

    def find(self, entity_id: EntityId) -> Entity | None:
        return next((entity for entity in self.entities if entity.id == entity_id), None)

    def thread(self, thread_id: Slug) -> Thread | None:
        return next((thread for thread in self.threads if thread.id == thread_id), None)

    def hook(self, hook_id: Slug) -> Hook | None:
        return next((hook for hook in self.hooks if hook.id == hook_id), None)

    def require(self, entity_id: EntityId) -> Entity:
        entity = self.find(entity_id)
        if entity is None:
            raise ValueError(f"unknown entity id {entity_id!r}. Use only ids you were shown.")
        return entity

    def require_kind(self, entity_id: EntityId, kind: Kind) -> Entity:
        entity = self.require(entity_id)
        if entity.kind != kind:
            raise ValueError(
                f"{entity_id!r} is a {entity.kind}, not a {kind}. "
                "Use an id of the kind this field asks for."
            )
        return entity

    def children(self, entity_id: EntityId, kind: Kind | None = None) -> tuple[Entity, ...]:
        held = self.entities if kind is None else self.of_kind(kind)
        return tuple(entity for entity in held if entity.parent_id == entity_id)

    def location_of(self, entity: Entity) -> EntityId | None:
        """Walk holders up to the enclosing place; a location is inside none, so it has none."""
        current = entity
        while current.parent_id is not None:
            current = self.require(current.parent_id)
        return None if current.id == entity.id else current.id


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
    # Ignored by dump and validate, so no persisted byte depends on the cache.
    _live_mechanics: Mutable | None = PrivateAttr(default=None)

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

    def mechanics_as[M: Mutable](self, model: type[M]) -> M:
        """One parsed mechanics per transaction, so a mutation cannot be lost by not writing it."""
        held = self._live_mechanics
        if isinstance(held, model):
            return held
        parsed = model.model_validate(self.mechanics)
        self._live_mechanics = parsed
        return parsed

    def set_mechanics(self, mechanics: Mutable) -> None:
        self._live_mechanics = mechanics

    def flush_mechanics(self) -> None:
        live = self._live_mechanics
        if live is None:
            return
        # Dumping runs no validator, so the dump is validated back: that is the commit gate.
        payload = live.model_dump(mode="json")
        _ = type(live).model_validate(payload)
        self.mechanics = payload

    def draft(self) -> Self:
        """A working copy a resolution mutates; a failed turn never replaces the committed state."""
        copied = self.model_copy(deep=True)
        copied._live_mechanics = None
        return copied

    def committed(self) -> Self:
        """One validation per transaction, over the whole copy rather than per field change."""
        self.flush_mechanics()
        return type(self).model_validate(self.model_dump(round_trip=True))

    def add(self, entity: Entity) -> Fact:
        """Copy into the fact, so a later move in the same turn cannot rewrite the entry."""
        if self.world.find(entity.id) is not None:
            raise ValueError(f"entity id {entity.id!r} already exists")
        self.world.entities.append(entity)
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
