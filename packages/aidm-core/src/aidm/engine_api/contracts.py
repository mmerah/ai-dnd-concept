from collections.abc import Callable
from random import Random
from typing import Protocol

from pydantic import BaseModel, Field
from pydantic_ai import RunContext
from pydantic_ai.output import OutputSpec

from ..agents.context import DirectorScene
from ..domain.base import EntityId
from ..domain.definitions import CharacterDefinition, ScenarioDefinition
from ..domain.direction import DirectionRecord
from ..domain.engine import EngineData, EngineRef, EngineStamp
from ..domain.entities import Entity
from ..domain.events import Event, RuleEvent, RuleStatePatch
from ..domain.state import GameState, WorldState
from ..utils.models import EMPTY_FROZEN_MAP, Frozen, FrozenMap


class EngineDescriptor(Frozen):
    ref: EngineRef
    schema_version: int = Field(ge=1)

    @classmethod
    def from_stamp(cls, stamp: EngineStamp) -> "EngineDescriptor":
        return cls(
            ref=EngineRef(id=stamp.id, rules_version=stamp.rules_version),
            schema_version=stamp.schema_version,
        )


class EngineInitialization(Frozen):
    game_rules: EngineData
    entity_rules: FrozenMap[EntityId, EngineData | None] = EMPTY_FROZEN_MAP


class EngineLifecycle(Protocol):
    def initialise(
        self,
        world: WorldState,
        scenario: ScenarioDefinition,
        character: CharacterDefinition,
    ) -> EngineInitialization: ...

    def rules_for_created_entity(
        self,
        entity: Entity,
        state: GameState,
    ) -> EngineData | None: ...


class EngineDirector(Protocol):
    @property
    def output(self) -> OutputSpec[BaseModel]: ...

    def instructions(self) -> str: ...

    def validate(
        self,
        ctx: RunContext[DirectorScene],
        direction: BaseModel,
    ) -> BaseModel: ...

    def record(self, direction: BaseModel) -> DirectionRecord: ...


class EngineRules(Protocol):
    def resolve(
        self,
        direction: BaseModel,
        state: GameState,
        rng: Random,
    ) -> list[Event]: ...

    def apply(self, state: GameState, event: RuleEvent) -> RuleStatePatch: ...

    def validate_state(self, state: GameState) -> None: ...


class EnginePresentation(Protocol):
    def entity_state(self, entity: Entity) -> str: ...
    def narrator_event(self, event: RuleEvent) -> str | None: ...
    def trace_event(self, event: RuleEvent) -> str: ...
    def trace_direction(self, direction: DirectionRecord) -> str: ...


class AdvancementStatus(Frozen):
    headline: str
    detail: tuple[str, ...] = ()
    progress: float = Field(default=0.0, ge=0.0, le=1.0)


class AdvancementEngine(Protocol):
    def available(self, state: GameState) -> bool: ...
    def status(self, state: GameState) -> AdvancementStatus: ...
    def preview(self, state: GameState) -> BaseModel: ...
    def plan(self, state: GameState, decisions: BaseModel) -> BaseModel: ...

    def advance(
        self,
        state: GameState,
        decisions: BaseModel,
        rng: Random,
    ) -> list[Event]: ...


class RulesEngine(Protocol):
    descriptor: EngineDescriptor

    @property
    def stamp(self) -> EngineStamp: ...

    @property
    def lifecycle(self) -> EngineLifecycle: ...

    @property
    def director(self) -> EngineDirector: ...

    @property
    def rules(self) -> EngineRules: ...

    @property
    def presentation(self) -> EnginePresentation: ...

    @property
    def advancement(self) -> AdvancementEngine | None: ...


type EngineFactory = Callable[[], RulesEngine]
