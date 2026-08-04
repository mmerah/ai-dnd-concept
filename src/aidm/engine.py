from collections.abc import Callable, Sequence
from dataclasses import dataclass
from random import Random

from pydantic_ai.toolsets import AbstractToolset

from .base import AdvancementDecision, EngineId, Entity
from .content import AuthoredWorld, Rules
from .facts import Fact
from .prompts import EntityRenderer
from .tools import TurnContext
from .transition import Transition
from .world import GameState, WorldState

NOTHING_MECHANICAL = "- (nothing mechanical happened)"

# True once the decision is committed; a rejected one leaves the panel's inputs intact.
type AdvancementSubmit = Callable[[AdvancementDecision], bool]
type CurrentState = Callable[[], GameState]
type AdvancementPanel = Callable[[CurrentState, AdvancementSubmit, Callable[[], None]], None]


def entered_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


@dataclass(frozen=True, slots=True)
class Engine:
    id: EngineId
    initial_world: Callable[[AuthoredWorld, Rules], WorldState]
    validate_state: Callable[[GameState], None]
    default_rules: Callable[[Entity], Rules]
    advance: Callable[[AdvancementDecision, GameState, Random], Transition]
    advancement_available: Callable[[GameState], bool]
    advancement_panel: AdvancementPanel
    director_toolset: AbstractToolset[TurnContext]
    director_instructions: str
    entity_state: Callable[[Entity, Rules], str]


def narrator_evidence(facts: Sequence[Fact]) -> str:
    lines = [f"- {rendered}" for fact in facts if (rendered := fact.narrator) is not None]
    return "\n".join(lines) or NOTHING_MECHANICAL


def entity_renderer(engine: Engine, state: GameState) -> EntityRenderer:
    return lambda entity: engine.entity_state(entity, state.world.record(entity.id).rules)
