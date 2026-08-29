from collections.abc import Callable, Iterator
from copy import deepcopy
from typing import Literal, Self

from pydantic import Field, ValidationError, model_validator

from aidm.state.entities import (
    DEAD,
    CheckedEntityId,
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
from aidm.state.play import Exchange, Line, PendingDecision

ThreadStatus = Literal["active", "resolved", "dormant"]


class Thread(Mutable):
    """A storyline the scenario tracks."""

    id: Slug
    title: str
    status: ThreadStatus = "active"
    note: str = ""


class AdvanceThread(Frozen):
    thread_id: Slug = Field(description="Exact id of an ACTIVE THREAD.")
    status: ThreadStatus | None = Field(
        default=None, description="New status, or null to keep the current status."
    )
    note: str | None = Field(
        default=None,
        description="New private note for the Director, or null to keep the current note.",
    )

    @model_validator(mode="after")
    def _moves_something(self) -> Self:
        if self.status is None and self.note is None:
            raise ValueError("advance-thread moves a thread's status or its note")
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
        for member_id in self.party:
            member = self.require_kind(member_id, "actor")
            if not member.known:
                raise ValueError(f"{member_id!r} travels with the player without being met")
            if member.trait(DEAD) is not None:
                raise ValueError(f"{member_id!r} is dead and cannot travel with the player")

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


class Game(Mutable):
    """The game as it is played, and the boundary a save on disk is validated through."""

    scenario_id: Slug
    character_id: Slug
    scenario: ScenarioMeta
    engine: EngineId
    packs: tuple[Slug, ...]
    # Which entity the player plays: it moves to a companion when the played character dies.
    player_id: CheckedEntityId
    world: WorldState
    # Cards of the turn in flight; a harness in another process reaches the page through the save.
    turn_events: tuple[MechanicEvent, ...]
    history: tuple[Exchange, ...] = ()
    turn: int = Field(default=0, ge=0)
    pending: PendingDecision | None = None

    @model_validator(mode="after")
    def _playable_game(self) -> Self:
        require_unique("game pack ids", self.packs)
        if "srd" not in self.packs:
            raise ValueError("game packs must include 'srd'")
        if not self.player.known:
            raise ValueError("the player entity must be known")
        if self.player_id in self.world.party:
            raise ValueError("the player cannot travel with themselves")
        return self

    @property
    def player(self) -> Entity:
        return self.world.require_kind(self.player_id, "actor")

    def label(self, entity: Entity) -> str:
        return labeled(entity, self.player_id)

    @property
    def player_location(self) -> EntityId:
        location = self.player.parent_id
        if location is None:
            raise ValueError("the player is not in a location")
        return location

    def is_here(self, entity: Entity) -> bool:
        return self.world.location_of(entity) == self.player_location

    def take_notes(self) -> tuple[str, ...]:
        """Notes are read once; a note a tool writes after this steers the next turn."""
        notes, self.world.pending_notes = self.world.pending_notes, ()
        return notes

    def record(
        self, prompt: str, lines: tuple[Line, ...], events: tuple[MechanicEvent, ...]
    ) -> None:
        """The one shape an exchange takes, whether a turn or the player's own action wrote it."""
        self.turn_events = ()
        self.history = (
            *self.history,
            Exchange(
                prompt=prompt,
                place=self.world.require(self.player_location).name,
                lines=lines,
                events=events,
                decision="" if self.pending is None else self.pending.prompt,
            ),
        )

    def draft(self) -> Self:
        """A working copy a resolution mutates; a failed turn never replaces the committed state."""
        return deepcopy(self)

    def committed(self) -> Self:
        """Dumping runs no validator, so the dump is validated back: that is the commit gate."""
        return type(self).model_validate(self.model_dump(round_trip=True))

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
        summary = f"learned of {self.label(entity)}"
        return [entity_fact(entity, "entity_discovered", summary)]

    def move(self, entity: Entity, destination: Entity) -> Fact:
        entity.parent_id = destination.id
        trace, card = _move_summary(self, entity, destination)
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


def _move_summary(state: Game, entity: Entity, destination: Entity) -> tuple[str, MechanicEvent]:
    """Trace (ids, for the Director) and card (plain names, for the player), from one branch."""
    icon = "directions_walk"
    if entity.kind == "actor":
        return (
            f"{state.label(entity)} moved to {state.label(destination)}",
            MechanicEvent(title=f"{entity.name} moved to {destination.name}", icon=icon),
        )
    if destination.id == state.player_id:
        return (
            f"{state.label(destination)} took {state.label(entity)}",
            MechanicEvent(title=f"Took {entity.name}", icon="back_hand"),
        )
    if destination.kind == "actor":
        # The giver is always the player: an item only ever moves to an actor by being handed over.
        return (
            f"the player gave {state.label(entity)} to {state.label(destination)}",
            MechanicEvent(title=f"Gave {entity.name} to {destination.name}", icon=icon),
        )
    return (
        f"the player left {state.label(entity)} at {state.label(destination)}",
        MechanicEvent(title=f"Left {entity.name} at {destination.name}", icon=icon),
    )
