from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
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

from . import bestiary, progression
from .access import dnd5e_state
from .advancement import Dnd5eAdvancement, Dnd5eAdvancementDecisions
from .content.library import load
from .content.pack_ruleset import compile_ruleset
from .direction import Dnd5eDirection
from .director import Dnd5eDirector
from .facts import Dnd5eFact
from .presentation import Dnd5ePresentation
from .rules import Dnd5eRules
from .ruleset import Ruleset
from .state import (
    Dnd5eActorDefinition,
    Dnd5eActorState,
    Dnd5eCharacterData,
    Dnd5eItemDefinition,
    Dnd5eItemState,
    Dnd5eState,
    StatBlock,
)

SHIPPED_PACK = Path(__file__).parent / "data" / "srd-2014"
ENGINE_ID: EngineId = "dnd5e"


@dataclass(frozen=True, slots=True)
class Dnd5eEngine:
    ruleset: Ruleset
    rules: Dnd5eRules
    director: Dnd5eDirector
    presentation: Dnd5ePresentation
    advancement: Dnd5eAdvancement
    id: ClassVar[EngineId] = ENGINE_ID

    def initial_state(
        self,
        authored: AuthoredWorld,
        character: CharacterEngineData,
    ) -> Dnd5eState:
        sheet = for_engine(character, Dnd5eCharacterData)
        start = progression.first_level(sheet, self.ruleset)
        actors: dict[EntityId, Dnd5eActorState] = {
            PLAYER_ID: Dnd5eActorState(
                stats=StatBlock(
                    attributes=start.attributes, max_hp=start.hp_gain, hp=start.hp_gain
                ),
                progression=start.progression,
            )
        }
        items: dict[EntityId, Dnd5eItemState] = {}
        for entity in authored.world.entities.values():
            data = authored.engine_data.get(entity.id)
            if isinstance(entity, ActorEntity) and entity.id != PLAYER_ID:
                actor = for_engine_or_none(data, Dnd5eActorDefinition)
                actors[entity.id] = bestiary.statted_actor(entity.id, actor, self.ruleset)
            elif isinstance(entity, ItemEntity):
                item = for_engine_or_none(data, Dnd5eItemDefinition)
                items[entity.id] = bestiary.statted_item(entity.id, item, self.ruleset)
        return Dnd5eState(actors=actors, items=items)

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
        return self.presentation.entity_state(entity, dnd5e_state(state))

    def narrator_fact(self, fact: Fact) -> str | None:
        return self.presentation.narrator_fact(_fact(fact))

    def trace_fact(self, fact: Fact) -> str:
        return self.presentation.trace_fact(_fact(fact))

    def trace_direction(self, direction: Direction) -> str:
        return self.presentation.trace_direction(_direction(direction))


def build_dnd5e_engine(pack_paths: Sequence[Path] | None = None) -> Dnd5eEngine:
    ruleset = compile_ruleset(load((SHIPPED_PACK,) if pack_paths is None else tuple(pack_paths)))
    return dnd5e_engine(ruleset)


def dnd5e_engine(ruleset: Ruleset) -> Dnd5eEngine:
    rules = Dnd5eRules(ruleset)
    return Dnd5eEngine(
        ruleset=ruleset,
        rules=rules,
        director=Dnd5eDirector(rules),
        presentation=Dnd5ePresentation(ruleset),
        advancement=Dnd5eAdvancement(ruleset),
    )


def _direction(direction: Direction) -> Dnd5eDirection:
    if not isinstance(direction, Dnd5eDirection):
        raise TypeError(f"{ENGINE_ID!r} engine received a {type(direction).__name__}")
    return direction


def _fact(fact: Fact) -> Dnd5eFact:
    if fact.source != "dnd5e":
        raise TypeError(f"{ENGINE_ID!r} engine received a {type(fact).__name__}")
    return fact


def _decision(decision: AdvancementDecision) -> Dnd5eAdvancementDecisions:
    if not isinstance(decision, Dnd5eAdvancementDecisions):
        raise TypeError(f"{ENGINE_ID!r} engine received a {type(decision).__name__}")
    return decision
