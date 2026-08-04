from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from random import Random

from pydantic_ai.toolsets import AbstractToolset

from .base import AdvancementDecision, EngineId, Entity
from .content import AuthoredWorld, Rules
from .facts import Fact
from .tools import TurnContext
from .world import EngineRules, GameState, WorldState

NOTHING_MECHANICAL = "- (nothing mechanical happened)"


@dataclass(frozen=True, slots=True)
class Transition[R: EngineRules]:
    state: GameState[R]
    facts: tuple[Fact, ...]


type EntityRenderer = Callable[[Entity], str]

# True once the decision is committed; a rejected one leaves the panel's inputs intact.
type AdvancementSubmit = Callable[[AdvancementDecision], bool]
type CurrentState = Callable[[], GameState[EngineRules]]
type AdvancementPanel = Callable[[CurrentState, AdvancementSubmit, Callable[[], None]], None]


def entered_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


@dataclass(frozen=True, slots=True)
class Engine[R: EngineRules]:
    id: EngineId
    state_type: type[GameState[R]]
    initial_world: Callable[[AuthoredWorld, Rules], WorldState[R]]
    validate_state: Callable[[GameState[R]], None]
    default_rules: Callable[[Entity], R]
    advance: Callable[[AdvancementDecision, GameState[R], Random], Transition[R]]
    advancement_available: Callable[[GameState[R]], bool]
    advancement_panel: AdvancementPanel
    toolsets: Mapping[str, AbstractToolset[TurnContext[R]]]
    director_instructions: str
    entity_state: Callable[[Entity, R], str]


def narrator_evidence(facts: Sequence[Fact]) -> str:
    lines = [f"- {rendered}" for fact in facts if (rendered := fact.narrator) is not None]
    return "\n".join(lines) or NOTHING_MECHANICAL


def entity_renderer[R: EngineRules](engine: Engine[R], state: GameState[R]) -> EntityRenderer:
    return lambda entity: engine.entity_state(entity, state.world.record(entity.id).rules)
