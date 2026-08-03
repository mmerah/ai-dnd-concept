from dataclasses import dataclass
from random import Random
from typing import ClassVar

from pydantic_ai import RunContext
from pydantic_ai.output import OutputSpec

from aidm.base import (
    ActorEntity,
    AdvancementDecision,
    EngineId,
    Entity,
    ItemEntity,
    LocationEntity,
)
from aidm.content import AuthoredActor, AuthoredItem, AuthoredWorld, compose_world
from aidm.transition import Direction, Fact, Transition
from aidm.world import (
    CharacterEngineData,
    EntityRules,
    GameState,
    WorldState,
    for_engine,
    for_engine_or_none,
)

from .advancement import StoryAdvancement, StoryAdvancementDecision, is_story_decision
from .direction import StoryDirection
from .director import StoryDirector
from .facts import StoryFact
from .presentation import StoryPresentation
from .rules import StoryRules
from .state import (
    DEFAULT_APPROACHES,
    StoryActorDefinition,
    StoryActorState,
    StoryCharacterData,
    StoryItemDefinition,
    StoryItemState,
)

ENGINE_ID: EngineId = "story"


@dataclass(frozen=True, slots=True)
class StoryEngine:
    rules: StoryRules
    director: StoryDirector
    presentation: StoryPresentation
    advancement: StoryAdvancement
    id: ClassVar[EngineId] = ENGINE_ID

    def initial_world(
        self,
        authored: AuthoredWorld,
        character: CharacterEngineData,
    ) -> WorldState:
        sheet = for_engine(character, StoryCharacterData)
        return compose_world(
            authored,
            StoryActorState(
                approaches=sheet.approaches,
                tags=sheet.tags,
                max_stress=sheet.max_stress,
            ),
            _actor_rules,
            _item_rules,
        )

    def validate_state(self, state: GameState) -> None:
        if state.engine != ENGINE_ID:
            raise ValueError(f"Story received a {state.engine!r} game")

    def default_rules(self, entity: Entity) -> EntityRules | None:
        match entity:
            case ActorEntity():
                return StoryActorState(approaches=DEFAULT_APPROACHES)
            case ItemEntity():
                return StoryItemState()
            case LocationEntity():
                return None

    def resolve(self, direction: Direction, state: GameState, rng: Random) -> Transition:
        return self.rules.resolve(_direction(direction), state, rng)

    def advance(
        self,
        decision: AdvancementDecision,
        state: GameState,
        rng: Random,
    ) -> Transition:
        return self.advancement.advance(state, _decision(decision), rng)

    def advancement_available(self, state: GameState) -> bool:
        return self.advancement.available(state)

    def director_output(self) -> OutputSpec[Direction]:
        return self.director.output

    def director_instructions(self) -> str:
        return self.director.instructions()

    def validate_direction(self, ctx: RunContext[GameState], direction: Direction) -> Direction:
        return self.director.validate(ctx, _direction(direction))

    def entity_state(self, entity: Entity, rules: EntityRules) -> str:
        return self.presentation.entity_state(entity, rules)

    def narrator_fact(self, fact: Fact) -> str | None:
        return self.presentation.narrator_fact(_fact(fact))

    def trace_fact(self, fact: Fact) -> str:
        return self.presentation.trace_fact(_fact(fact))

    def trace_direction(self, direction: Direction) -> str:
        return self.presentation.trace_direction(_direction(direction))


def build_story_engine() -> StoryEngine:
    rules = StoryRules()
    return StoryEngine(
        rules=rules,
        director=StoryDirector(rules),
        presentation=StoryPresentation(),
        advancement=StoryAdvancement(),
    )


def _actor_rules(authored: AuthoredActor) -> StoryActorState:
    definition = for_engine_or_none(authored.data, StoryActorDefinition)
    if definition is None:
        return StoryActorState(approaches=DEFAULT_APPROACHES)
    return definition.runtime()


def _item_rules(authored: AuthoredItem) -> StoryItemState:
    definition = for_engine_or_none(authored.data, StoryItemDefinition)
    return StoryItemState() if definition is None else definition.runtime()


def _direction(direction: Direction) -> StoryDirection:
    if not isinstance(direction, StoryDirection):
        raise TypeError(f"{ENGINE_ID!r} engine received a {type(direction).__name__}")
    return direction


def _fact(fact: Fact) -> StoryFact:
    if fact.source != "story":
        raise TypeError(f"{ENGINE_ID!r} engine received a {type(fact).__name__}")
    return fact


def _decision(decision: AdvancementDecision) -> StoryAdvancementDecision:
    if not is_story_decision(decision):
        raise TypeError(f"{ENGINE_ID!r} engine received a {type(decision).__name__}")
    return decision
