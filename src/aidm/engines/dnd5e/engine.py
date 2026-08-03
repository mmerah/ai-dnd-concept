from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
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
from aidm.transition import Direction, Transition
from aidm.world import (
    CharacterEngineData,
    EntityRules,
    GameState,
    WorldState,
    for_engine,
    for_engine_or_none,
)

from . import bestiary, progression
from .advancement import Dnd5eAdvancement, Dnd5eAdvancementDecisions
from .content.library import load
from .content.pack_ruleset import compile_ruleset
from .direction import Dnd5eDirection
from .director import Dnd5eDirector
from .presentation import Dnd5ePresentation
from .rules import Dnd5eRules
from .ruleset import Ruleset
from .state import (
    Dnd5eActorDefinition,
    Dnd5eActorState,
    Dnd5eCharacterData,
    Dnd5eItemDefinition,
    Dnd5eItemState,
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

    def initial_world(
        self,
        authored: AuthoredWorld,
        character: CharacterEngineData,
    ) -> WorldState:
        sheet = for_engine(character, Dnd5eCharacterData)
        start = progression.first_level(sheet, self.ruleset)
        return compose_world(
            authored,
            Dnd5eActorState(
                stats=StatBlock(
                    attributes=start.attributes, max_hp=start.hp_gain, hp=start.hp_gain
                ),
                progression=start.progression,
            ),
            self._actor_rules,
            self._item_rules,
        )

    def validate_state(self, state: GameState) -> None:
        if state.engine != ENGINE_ID:
            raise ValueError(f"5e received a {state.engine!r} game")
        self.rules.validate_state(state)

    def default_rules(self, entity: Entity) -> EntityRules | None:
        match entity:
            case ActorEntity():
                return Dnd5eActorState(stats=StatBlock())
            case ItemEntity():
                return Dnd5eItemState()
            case LocationEntity():
                return None

    def _actor_rules(self, authored: AuthoredActor) -> Dnd5eActorState:
        definition = for_engine_or_none(authored.data, Dnd5eActorDefinition)
        return bestiary.statted_actor(authored.entity.id, definition, self.ruleset)

    def _item_rules(self, authored: AuthoredItem) -> Dnd5eItemState:
        definition = for_engine_or_none(authored.data, Dnd5eItemDefinition)
        return bestiary.statted_item(authored.entity.id, definition, self.ruleset)

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


def _decision(decision: AdvancementDecision) -> Dnd5eAdvancementDecisions:
    if not isinstance(decision, Dnd5eAdvancementDecisions):
        raise TypeError(f"{ENGINE_ID!r} engine received a {type(decision).__name__}")
    return decision
