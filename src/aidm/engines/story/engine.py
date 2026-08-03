from dataclasses import dataclass
from random import Random
from typing import ClassVar

from pydantic_ai import RunContext
from pydantic_ai.output import OutputSpec

from aidm.base import (
    PLAYER_ID,
    ActorEntity,
    AdvancementDecision,
    EngineId,
    Entity,
    EntityId,
    ItemEntity,
)
from aidm.content import AuthoredWorld
from aidm.transition import Direction, Fact, Transition
from aidm.world import CharacterEngineData, GameState, for_engine, for_engine_or_none

from .access import story_state
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
    StoryState,
)

ENGINE_ID: EngineId = "story"


@dataclass(frozen=True, slots=True)
class StoryEngine:
    rules: StoryRules
    director: StoryDirector
    presentation: StoryPresentation
    advancement: StoryAdvancement
    id: ClassVar[EngineId] = ENGINE_ID

    def initial_state(
        self,
        authored: AuthoredWorld,
        character: CharacterEngineData,
    ) -> StoryState:
        sheet = for_engine(character, StoryCharacterData)
        actors: dict[EntityId, StoryActorState] = {
            PLAYER_ID: StoryActorState(
                approaches=sheet.approaches,
                tags=sheet.tags,
                max_stress=sheet.max_stress,
            )
        }
        items: dict[EntityId, StoryItemState] = {}
        for entity in authored.world.entities.values():
            data = authored.engine_data.get(entity.id)
            if isinstance(entity, ActorEntity) and entity.id != PLAYER_ID:
                actor = for_engine_or_none(data, StoryActorDefinition)
                actors[entity.id] = (
                    StoryActorState(approaches=DEFAULT_APPROACHES)
                    if actor is None
                    else actor.runtime()
                )
            elif isinstance(entity, ItemEntity):
                item = for_engine_or_none(data, StoryItemDefinition)
                items[entity.id] = StoryItemState() if item is None else item.runtime()
        return StoryState(actors=actors, items=items)

    def validate_state(self, state: GameState) -> None:
        self.rules.validate_state(state)

    def created(self, draft: GameState, entity: Entity) -> None:
        self.rules.created(draft, entity)

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

    def entity_state(self, entity: Entity, state: GameState) -> str:
        return self.presentation.entity_state(entity, story_state(state))

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
