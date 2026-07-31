import json
from pathlib import Path
from random import Random
from typing import Annotated

from pydantic import BaseModel, Field, SecretStr, TypeAdapter
from pydantic_ai import NativeOutput, RunContext
from pydantic_ai.output import OutputSpec

from aidm.agents.context import DirectorScene
from aidm.config import ProviderConfig, Providers, Roles, Settings
from aidm.domain.actions import (
    CoreActionUnion,
    is_core_action,
    resolve_core_action,
)
from aidm.domain.base import EntityId
from aidm.domain.definitions import (
    CharacterDefinition,
    ScenarioDefinition,
    ScenarioMeta,
)
from aidm.domain.direction import DirectionRecord
from aidm.domain.engine import EngineData, EngineRef, EngineStamp
from aidm.domain.entities import (
    ActorDefinition,
    ActorEntity,
    Entity,
    ItemDefinition,
    ItemEntity,
    LocationDefinition,
)
from aidm.domain.events import Event, RuleEvent, RuleStatePatch
from aidm.domain.json import thaw_json
from aidm.domain.reducer import apply
from aidm.domain.state import GameState, WorldState, attach_initial_rules, world_from_definitions
from aidm.engine_api.codec import EngineCodec
from aidm.engine_api.contracts import (
    EngineDescriptor,
    EngineInitialization,
)
from aidm.utils.models import Frozen

ENGINE_ID = "test-engine"
SCHEMA_VERSION = 1
STAMP = EngineStamp(
    id=ENGINE_ID,
    rules_version=1,
    schema_version=SCHEMA_VERSION,
)
DESCRIPTOR = EngineDescriptor.from_stamp(STAMP)


class TestRulesData(Frozen):
    value: int = 0


RULES_CODEC = EngineCodec(
    TestRulesData,
    engine=ENGINE_ID,
    schema_version=SCHEMA_VERSION,
)

type TestAction = Annotated[CoreActionUnion, Field(discriminator="action")]
ACTION_ADAPTER: TypeAdapter[list[TestAction]] = TypeAdapter(list[TestAction])


class TestDirection(Frozen):
    intent: str
    tone: str
    speaker_id: EntityId | None = None
    mechanics: list[TestAction] = Field(default_factory=list)


class TestLifecycle:
    def initialise(
        self,
        world: WorldState,
        scenario: ScenarioDefinition,
        character: CharacterDefinition,
    ) -> EngineInitialization:
        del scenario, character
        entity_rules = {
            entity.id: (
                RULES_CODEC.encode(TestRulesData())
                if isinstance(entity, ActorEntity | ItemEntity)
                else None
            )
            for entity in world.entities.values()
        }
        return EngineInitialization(
            game_rules=RULES_CODEC.encode(TestRulesData()),
            entity_rules=entity_rules,
        )

    def rules_for_created_entity(
        self,
        entity: Entity,
        state: GameState,
    ) -> EngineData | None:
        if state.engine != STAMP:
            raise ValueError("test lifecycle received an incompatible state")
        if isinstance(entity, ActorEntity | ItemEntity):
            return RULES_CODEC.encode(TestRulesData())
        return None


class TestRules:
    def __init__(self, lifecycle: TestLifecycle) -> None:
        self._lifecycle = lifecycle

    def resolve(
        self,
        direction: BaseModel,
        state: GameState,
        rng: Random,
    ) -> list[Event]:
        del rng
        if not isinstance(direction, TestDirection):
            raise TypeError(f"test rules received {type(direction).__name__}")
        emitted: list[Event] = []
        provisional = state
        for action in direction.mechanics:
            events = resolve_core_action(
                action,
                provisional,
                self._lifecycle.rules_for_created_entity,
            )
            emitted.extend(events)
            provisional = apply(provisional, events, self)
        return emitted

    def apply(self, state: GameState, event: RuleEvent) -> RuleStatePatch:
        del state, event
        return RuleStatePatch()

    def validate_state(self, state: GameState) -> None:
        RULES_CODEC.decode(state.rules)
        for entity in state.world.entities.values():
            if isinstance(entity, ActorEntity | ItemEntity):
                if entity.rules is None:
                    raise ValueError(f"test entity {entity.id!r} has no rules data")
                RULES_CODEC.decode(entity.rules)
            elif entity.rules is not None:
                raise ValueError(f"test location {entity.id!r} has rules data")


class TestDirector:
    @property
    def output(self) -> OutputSpec[BaseModel]:
        return NativeOutput(TestDirection)

    def instructions(self) -> str:
        return "Use the typed test actions."

    def validate(
        self,
        ctx: RunContext[DirectorScene],
        direction: BaseModel,
    ) -> BaseModel:
        del ctx
        if not isinstance(direction, TestDirection):
            raise TypeError(f"test Director received {type(direction).__name__}")
        if not all(is_core_action(action) for action in direction.mechanics):
            raise TypeError("test Director received a non-core action")
        return direction

    def record(self, direction: BaseModel) -> DirectionRecord:
        if not isinstance(direction, TestDirection):
            raise TypeError(f"test Director received {type(direction).__name__}")
        mechanics: object = json.loads(ACTION_ADAPTER.dump_json(direction.mechanics))
        return DirectionRecord.model_validate(
            {
                "engine": ENGINE_ID,
                "schema_version": SCHEMA_VERSION,
                "intent": direction.intent,
                "tone": direction.tone,
                "speaker_id": direction.speaker_id,
                "mechanics": mechanics,
            }
        )


class TestPresentation:
    def entity_state(self, entity: Entity) -> str:
        if entity.rules is None:
            return ""
        return f"value {RULES_CODEC.decode(entity.rules).value}"

    def narrator_event(self, event: RuleEvent) -> str | None:
        del event
        return None

    def trace_event(self, event: RuleEvent) -> str:
        return event.name

    def trace_direction(self, direction: DirectionRecord) -> str:
        return json.dumps(thaw_json(direction.mechanics))


class TestEngine:
    descriptor = DESCRIPTOR

    def __init__(self) -> None:
        lifecycle = TestLifecycle()
        self._lifecycle = lifecycle
        self._rules = TestRules(lifecycle)
        self._director = TestDirector()
        self._presentation = TestPresentation()

    @property
    def stamp(self) -> EngineStamp:
        return STAMP

    @property
    def lifecycle(self) -> TestLifecycle:
        return self._lifecycle

    @property
    def director(self) -> TestDirector:
        return self._director

    @property
    def rules(self) -> TestRules:
        return self._rules

    @property
    def presentation(self) -> TestPresentation:
        return self._presentation

    @property
    def advancement(self) -> None:
        return None


def scenario() -> ScenarioDefinition:
    return ScenarioDefinition(
        meta=ScenarioMeta(title="The Test Vault", premise="A deterministic test scenario."),
        engine=EngineRef(id=ENGINE_ID, rules_version=1),
        starting_location_id=EntityId("study"),
        entities=(
            LocationDefinition(
                id=EntityId("study"),
                name="the study",
                brief="A quiet room.",
                known=True,
            ),
            LocationDefinition(
                id=EntityId("vault"),
                name="the vault",
                brief="A sealed chamber.",
            ),
            ActorDefinition(
                id=EntityId("mara"),
                name="Mara",
                brief="A cautious scribe.",
                known=True,
                location_id=EntityId("study"),
            ),
            ActorDefinition(
                id=EntityId("elena"),
                name="Elena",
                brief="A hidden archivist.",
                location_id=EntityId("vault"),
            ),
            ItemDefinition(
                id=EntityId("vault_map"),
                name="the vault map",
                brief="A creased chart.",
                container_id=EntityId("study"),
            ),
        ),
    )


def character() -> CharacterDefinition:
    return CharacterDefinition.model_validate(
        {
            "name": "Kael",
            "brief": "A relic-hunter.",
            "engine": {"id": ENGINE_ID, "rules_version": 1},
            "engine_data": RULES_CODEC.encode(TestRulesData()),
            "starting_items": [
                {
                    "name": "a guttering lantern",
                    "brief": "A dented lantern.",
                    "engine_data": RULES_CODEC.encode(TestRulesData()),
                }
            ],
        }
    )


def initialized() -> tuple[TestEngine, GameState]:
    selected_scenario = scenario()
    selected_character = character()
    engine = TestEngine()
    world = world_from_definitions(selected_scenario, selected_character)
    initial = engine.lifecycle.initialise(world, selected_scenario, selected_character)
    state = GameState(
        engine=engine.stamp,
        scenario=selected_scenario.meta,
        world=attach_initial_rules(world, initial.entity_rules, engine.stamp),
        rules=initial.game_rules,
    )
    engine.rules.validate_state(state)
    return engine, state


def settings() -> Settings:
    return Settings(
        providers=Providers(
            openrouter=ProviderConfig(
                base_url="https://example.invalid/v1",
                api_key=SecretStr("test"),
            )
        ),
        roles=Roles(),
        max_growth=3,
        history_window=6,
        saves_dir=Path("saves"),
        scenarios_dir=Path("scenarios"),
        characters_dir=Path("characters"),
    )
