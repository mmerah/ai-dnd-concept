from collections.abc import Callable, Iterator
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Literal, Self

from pydantic import Field, ValidationError, model_validator

from aidm.state.entities import (
    PLAYER_ID,
    Counter,
    EngineId,
    Entity,
    EntityId,
    Frozen,
    Kind,
    Mutable,
    Slug,
    check_placement,
    kind_word,
    require_unique,
)
from aidm.state.facts import Fact, MechanicEvent, entity_fact, labeled
from aidm.state.play import Exchange, PendingDecision

ThreadStatus = Literal["active", "resolved", "dormant"]


class Thread(Mutable):
    """A storyline the scenario tracks."""

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
    thread_id: Slug = Field(description="Exact id of an ACTIVE THREAD.")
    status: ThreadStatus | None = Field(
        default=None, description="New status, or null to keep the current status."
    )
    stage: Slug | None = Field(
        default=None,
        description="New stage slug, or null to keep the current stage.",
    )
    tick: int = Field(
        default=0,
        description="Number of segments to fill on its clock. Use 0 for no change.",
    )
    note: str | None = Field(
        default=None,
        description="New private note for the Director, or null to keep the current note.",
    )

    @model_validator(mode="after")
    def _moves_something(self) -> Self:
        if self.tick < 0:
            raise ValueError("a tick fills a clock; it never runs one backwards")
        if self.status is None and self.stage is None and not self.tick:
            raise ValueError("advance-thread moves a thread's status, its stage, or its clock")
        return self


class WorldState(Mutable):
    """The whole persistent fiction; `Game` holds the played game around it."""

    entities: list[Entity] = Field(default_factory=list)
    threads: list[Thread] = Field(default_factory=list)
    party: list[EntityId] = Field(default_factory=list)
    pending_notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _consistent_fiction(self) -> Self:
        require_unique("entity ids", (entity.id for entity in self.entities))
        require_unique("thread ids", (thread.id for thread in self.threads))
        for entity in self.entities:
            # `find`, not `require`: a dangling id is a topology fault, not a lookup failure.
            holder = None if entity.parent_id is None else self.find(entity.parent_id)
            check_placement(entity, holder)
            self._check_exits(entity)
        self._check_party()
        return self

    def _check_exits(self, entity: Entity) -> None:
        """Reject known exits that would expose an unknown destination."""
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


def check_player_playable(world: WorldState) -> None:
    if not world.require_kind(PLAYER_ID, "actor").known:
        raise ValueError("the player entity must be known")


def frontier(world: WorldState) -> int:
    """Unknown locations a known location leads to: doors the player can still find."""
    known = {entity.id for entity in world.entities if entity.known}
    return len(
        {
            way.to
            for entity in world.entities
            if entity.id in known
            for way in entity.exits
            if not world.require(way.to).known
        }
    )


class ScenarioMeta(Frozen):
    title: str
    premise: str


@dataclass(slots=True)
class Game:
    """The game as it is played; `SavedGame` is the boundary that validates one."""

    scenario_id: Slug
    character_id: Slug
    scenario: ScenarioMeta
    engine: EngineId
    world: WorldState
    # Opaque to core: the engine that wrote it is the only reader and the only validator.
    mechanics: Mutable
    history: tuple[Exchange, ...] = ()
    turn: int = 0
    pending: PendingDecision | None = None

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
        return deepcopy(self)

    def committed(self) -> Self:
        """One validation per transaction, over the whole copy rather than per field change."""
        landed = replace(
            self,
            world=_revalidated(self.world),
            mechanics=_revalidated(self.mechanics),
        )
        check_player_playable(landed.world)
        return landed

    def add(self, entity: Entity) -> Fact:
        """Copy into the fact, so a later move in the same turn cannot rewrite the entry."""
        if self.world.find(entity.id) is not None:
            raise ValueError(f"entity id {entity.id!r} already exists")
        self.world.entities.append(entity)
        summary = f"new {kind_word(entity.kind)}: {entity.name}[{entity.id}]"
        return entity_fact(entity, "entity_created", summary)

    def reveal(self, entity: Entity) -> list[Fact]:
        """Leave cards to the containing action or the standalone reveal resolver."""
        if entity.known:
            return []
        entity.known = True
        summary = f"learned of {labeled(entity)}"
        return [entity_fact(entity, "entity_discovered", summary)]

    def move(self, entity: Entity, destination: Entity) -> Fact:
        entity.parent_id = destination.id
        trace, card = _move_summary(entity, destination)
        return entity_fact(entity, "entity_moved", trace, event=card)


def draft_refusal(
    state: Game, mutate: Callable[[Game], object], what: str = "the state this leaves"
) -> str | None:
    draft = state.draft()
    try:
        _ = mutate(draft)
        _ = draft.committed()
    except ValidationError as broken:
        return f"{what} is invalid: {broken.errors()[0]['msg']}"
    except ValueError as refused:
        return str(refused)
    return None


def _revalidated[M: Mutable](model: M) -> M:
    """Dumping runs no validator, so the dump is validated back: that is the commit gate."""
    return type(model).model_validate(model.model_dump(round_trip=True))


def _move_summary(entity: Entity, destination: Entity) -> tuple[str, MechanicEvent]:
    """Trace (ids, for the Director) and card (plain names, for the player), from one branch."""
    icon = "directions_walk"
    if entity.kind == "actor":
        return (
            f"{labeled(entity)} moved to {labeled(destination)}",
            MechanicEvent(title=f"{entity.name} moved to {destination.name}", icon=icon),
        )
    if destination.id == PLAYER_ID:
        return (
            f"{labeled(destination)} took {labeled(entity)}",
            MechanicEvent(title=f"Took {entity.name}", icon="back_hand"),
        )
    if destination.kind == "actor":
        # The giver is always the player: an item only ever moves to an actor by being handed over.
        return (
            f"the player gave {labeled(entity)} to {labeled(destination)}",
            MechanicEvent(title=f"Gave {entity.name} to {destination.name}", icon=icon),
        )
    return (
        f"the player left {labeled(entity)} at {labeled(destination)}",
        MechanicEvent(title=f"Left {entity.name} at {destination.name}", icon=icon),
    )
