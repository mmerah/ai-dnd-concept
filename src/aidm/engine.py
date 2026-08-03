from collections.abc import Callable, Sequence
from dataclasses import dataclass
from random import Random

from pydantic_ai.output import OutputSpec

from .advancement import AdvancementChoice, AdvancementForm, AdvancementReview, AdvancementStatus
from .base import AdvancementDecision, EngineId, Entity
from .content import AuthoredWorld, Rules
from .facts import Fact
from .prompts import EntityRenderer
from .transition import Direction, Transition
from .world import GameState, WorldState

NOTHING_MECHANICAL = "- (nothing mechanical happened)"


@dataclass(frozen=True, slots=True)
class Engine:
    """One flat engine seam; the plugin's build fills every field from its own collaborators."""

    id: EngineId
    initial_world: Callable[[AuthoredWorld, Rules], WorldState]
    validate_state: Callable[[GameState], None]
    default_rules: Callable[[Entity], Rules]
    resolve: Callable[[Direction, GameState, Random], Transition]
    advance: Callable[[AdvancementDecision, GameState, Random], Transition]
    advancement_available: Callable[[GameState], bool]
    advancement_status: Callable[[GameState], AdvancementStatus]
    advancement_form: Callable[[GameState], AdvancementForm]
    advancement_review: Callable[[GameState, AdvancementChoice], AdvancementReview]
    director_output: OutputSpec[Direction]
    director_instructions: str
    entity_state: Callable[[Entity, Rules], str]


def narrator_evidence(facts: Sequence[Fact]) -> str:
    lines = [f"- {rendered}" for fact in facts if (rendered := fact.narrator) is not None]
    return "\n".join(lines) or NOTHING_MECHANICAL


def entity_renderer(engine: Engine, state: GameState) -> EntityRenderer:
    return lambda entity: engine.entity_state(entity, state.world.record(entity.id).rules)
