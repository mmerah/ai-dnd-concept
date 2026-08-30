from collections.abc import Callable, Iterator, Sequence
from copy import deepcopy
from typing import Literal, Self

from pydantic import (
    BaseModel,
    Field,
    JsonValue,
    SerializeAsAny,
    ValidationError,
    field_validator,
    model_validator,
)

from aidm.state.entities import (
    PLAYER_ID,
    CheckedEntityId,
    EngineId,
    Entity,
    EntityId,
    Frozen,
    Kind,
    Mutable,
    Slug,
    Trait,
    kind_word,
    require_unique,
)
from aidm.state.facts import Fact, cards, entity_fact, labeled
from aidm.state.play import Exchange, PendingDecision, Speaker, SpokenLine

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


type Mechanics = dict[str, JsonValue]
# (blob, added, removed ids) -> blob. One operation, so a rejected patch leaves nothing behind.
type MechanicsPatch = Callable[[Mechanics, Mechanics, Sequence[EntityId]], Mechanics]


class WorldState(Mutable):
    """The whole persistent fiction; `Game` holds the played game around it."""

    entities: dict[EntityId, Entity] = Field(default_factory=dict)
    threads: dict[Slug, Thread] = Field(default_factory=dict)
    party: list[EntityId] = Field(default_factory=list)
    # Engine-owned JSON: core never reads inside it.
    mechanics: Mechanics = Field(default_factory=dict)

    @model_validator(mode="after")
    def _consistent_fiction(self) -> Self:
        """Only what holds without room semantics; `world.topology` owns the rooms rules."""
        for key, entity in self.entities.items():
            if key != entity.id:
                raise ValueError(f"entity {entity.id!r} is filed under {key!r}")
            self._check_chain(entity)
        for key, thread in self.threads.items():
            if key != thread.id:
                raise ValueError(f"thread {thread.id!r} is filed under {key!r}")
        return self

    def _check_chain(self, entity: Entity) -> None:
        seen = {entity.id}
        current = entity
        while current.parent_id is not None:
            if current.parent_id in seen:
                raise ValueError(f"{entity.id!r} is inside itself through its holders")
            current = self.require(current.parent_id)
            seen.add(current.id)

    def of_kind(self, kind: Kind) -> Iterator[Entity]:
        return (entity for entity in self.entities.values() if entity.kind == kind)

    def all_ids(self) -> set[EntityId]:
        return set(self.entities)

    def find(self, entity_id: EntityId) -> Entity | None:
        return self.entities.get(entity_id)

    def thread(self, thread_id: Slug) -> Thread | None:
        return self.threads.get(thread_id)

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


class ScenarioMeta(Frozen):
    title: str
    premise: str


def require_parsed_payload(value: object) -> object:
    """A bare BaseModel would swallow a dict whole; the engine parses its payload first."""
    if not isinstance(value, BaseModel):
        raise ValueError("the engine parses the payload before the model holds it")
    return value


class WorldPayload(Mutable):
    """The legacy engines' save payload; it dies with the Phase-3 port to typed engine states."""

    # Which entity the player plays: it moves to a companion when the played character dies.
    player_id: CheckedEntityId
    world: WorldState

    @model_validator(mode="after")
    def _playable(self) -> Self:
        if not self.world.require_kind(self.player_id, "actor").known:
            raise ValueError("the player entity must be known")
        if self.player_id in self.world.party:
            raise ValueError("the player cannot travel with themselves")
        return self


class ScenarioPayload(Frozen):
    """The legacy engines' scenario payload; it dies with the Phase-3 port."""

    # Where the played character starts; a non-rooms engine leaves it null.
    player_parent_id: CheckedEntityId | None = None
    # Shared by every game of this scenario: read-only — `begin_game` deep-copies before mutating.
    world: WorldState

    @model_validator(mode="after")
    def _playable_canon(self) -> Self:
        if self.world.find(PLAYER_ID) is not None:
            raise ValueError(f"an entity claims the reserved player id {PLAYER_ID!r}")
        if self.player_parent_id is not None:
            _ = self.world.require(self.player_parent_id)
        return self


class Scenario(Frozen):
    """`scenarios/<id>/world.json`: its dump is the scenario envelope around one payload."""

    meta: ScenarioMeta
    engine: EngineId
    packs: tuple[Slug, ...] = Field(min_length=1)
    grows: bool = False
    art_style: str = ""
    payload: SerializeAsAny[BaseModel]

    _payload_is_parsed = field_validator("payload", mode="before")(require_parsed_payload)

    @model_validator(mode="after")
    def _unique_packs(self) -> Self:
        require_unique("scenario pack ids", self.packs)
        return self

    @property
    def _legacy(self) -> ScenarioPayload:
        if not isinstance(self.payload, ScenarioPayload):
            raise ValueError(f"the {self.engine!r} scenario holds no rooms world")
        return self.payload

    @property
    def world(self) -> WorldState:
        return self._legacy.world

    @property
    def player_parent_id(self) -> CheckedEntityId | None:
        return self._legacy.player_parent_id


class CharacterPayload(Frozen):
    """The legacy engines' character payload; it dies with the Phase-3 port."""

    traits: tuple[Trait, ...] = ()
    items: tuple[Entity, ...] = ()
    mechanics: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _held_and_known(self) -> Self:
        """Reject unknown carried gear because the Narrator sees the inventory."""
        wrong_kind = sorted(item.id for item in self.items if item.kind != "item")
        if wrong_kind:
            raise ValueError(f"a character holds items only: {wrong_kind}")
        misplaced = sorted(item.id for item in self.items if item.parent_id != PLAYER_ID)
        if misplaced:
            raise ValueError(f"a character's items start in their own hands: {misplaced}")
        unknown = sorted(item.id for item in self.items if not item.known)
        if unknown:
            raise ValueError(f"a character knows the gear they start with: {unknown}")
        return self


class Character(Frozen):
    """`characters/<id>/<engine>.json`: who they are and the payload this engine plays them by."""

    id: Slug
    engine: EngineId
    name: str
    brief: str
    payload: SerializeAsAny[BaseModel]

    _payload_is_parsed = field_validator("payload", mode="before")(require_parsed_payload)

    @property
    def _legacy(self) -> CharacterPayload:
        if not isinstance(self.payload, CharacterPayload):
            raise ValueError(f"the {self.engine!r} character holds no legacy payload")
        return self.payload

    @property
    def traits(self) -> tuple[Trait, ...]:
        return self._legacy.traits

    @property
    def items(self) -> tuple[Entity, ...]:
        return self._legacy.items

    @property
    def mechanics(self) -> dict[str, JsonValue]:
        return self._legacy.mechanics


class Game(Mutable):
    """The game as it is played; its dump is the save envelope around one engine payload."""

    scenario_id: Slug
    character_id: Slug
    scenario: ScenarioMeta
    engine: EngineId
    packs: tuple[Slug, ...] = Field(min_length=1)
    turn: int = Field(default=0, ge=0)
    history: tuple[Exchange, ...] = ()
    # Cards of the turn in flight; a harness in another process reaches the page through the save.
    turn_facts: tuple[Fact, ...]
    pending: PendingDecision | None = None
    notes: tuple[str, ...] = ()
    payload: SerializeAsAny[BaseModel]

    _payload_is_parsed = field_validator("payload", mode="before")(require_parsed_payload)

    @model_validator(mode="after")
    def _playable_game(self) -> Self:
        require_unique("game pack ids", self.packs)
        return self

    @property
    def _legacy(self) -> WorldPayload:
        if not isinstance(self.payload, WorldPayload):
            raise ValueError(f"the {self.engine!r} state holds no rooms world")
        return self.payload

    @property
    def world(self) -> WorldState:
        return self._legacy.world

    @property
    def player_id(self) -> EntityId:
        return self._legacy.player_id

    @player_id.setter
    def player_id(self, value: EntityId) -> None:
        self._legacy.player_id = value

    @property
    def player(self) -> Entity:
        return self.world.require_kind(self.player_id, "actor")

    def label(self, entity: Entity) -> str:
        return labeled(entity, self.player_id)

    def take_notes(self) -> tuple[str, ...]:
        """Notes are read once; a note a tool writes after this steers the next turn."""
        notes, self.notes = self.notes, ()
        return notes

    def record(
        self,
        scene_label: str,
        prompt: str,
        speaker: Speaker,
        lines: tuple[SpokenLine, ...],
        facts: tuple[Fact, ...],
    ) -> None:
        """The one shape an exchange takes, whether a turn or the player's own action wrote it."""
        self.turn_facts = ()
        self.history = (
            *self.history,
            Exchange(
                prompt=prompt,
                speaker=speaker,
                scene=scene_label,
                lines=lines,
                facts=cards(facts),
                decision="" if self.pending is None else self.pending.prompt,
            ),
        )

    def draft(self) -> Self:
        """A working copy a resolution mutates; a failed turn never replaces the committed state."""
        return deepcopy(self)

    def committed(self) -> Self:
        """Dumping runs no validator, so the dump is validated back: that is the commit gate."""
        dumped = self.model_dump(round_trip=True)
        dumped["payload"] = type(self.payload).model_validate(dumped["payload"])
        return type(self).model_validate(dumped)

    def add(self, entity: Entity) -> Fact:
        """Copy into the fact, so a later move in the same turn cannot rewrite the entry."""
        if entity.id in self.world.entities:
            raise ValueError(f"entity id {entity.id!r} already exists")
        self.world.entities[entity.id] = entity
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
        return entity_fact(entity, "entity_moved", trace, card=card)


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


def _move_summary(state: Game, entity: Entity, destination: Entity) -> tuple[str, str]:
    """Trace (ids, for the Director) and card (plain names, for the player), from one branch."""
    if entity.kind == "actor":
        card = (
            f"{entity.name} moved to {destination.name}"
            if destination.known
            else f"{entity.name} leaves"
        )
        return f"{state.label(entity)} moved to {state.label(destination)}", card
    if destination.id == state.player_id:
        return f"{state.label(destination)} took {state.label(entity)}", f"Took {entity.name}"
    if destination.kind == "actor":
        # The giver is always the player: an item only ever moves to an actor by being handed over.
        card = (
            f"Gave {entity.name} to {destination.name}"
            if destination.known
            else f"Gave away {entity.name}"
        )
        return f"the player gave {state.label(entity)} to {state.label(destination)}", card
    return (
        f"the player left {state.label(entity)} at {state.label(destination)}",
        f"Left {entity.name} at {destination.name}",
    )
