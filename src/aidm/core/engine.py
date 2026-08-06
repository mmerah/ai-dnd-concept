from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from random import Random
from typing import Self

from pydantic import Field, ValidationError, model_validator
from pydantic_ai.toolsets import AbstractToolset

from .base import EngineId, Entity, Frozen
from .content import AuthoredWorld, Rules
from .facts import Fact
from .packs import ContentRef
from .plan import TurnPlanBase
from .sheet import AddRef, Sheet, SheetDelta, apply_delta
from .world import GameState, WorldState, player_sheet

NOTHING_MECHANICAL = "- (nothing mechanical happened)"

type EntityRenderer = Callable[[Entity], str]
type PlanCheck = Callable[[GameState, TurnPlanBase], str | None]
"""Judges the untouched committed state and returns the refusal. It must not raise: an output
validator turns an exception into a dead turn instead of a retry."""
type ActionResolver = Callable[[GameState, TurnPlanBase, Random], list[Fact]]
"""Mutates the draft: the action's rolls, its intrinsic consequences, and the branch taken."""


class AdvancementOffer(Frozen):
    """One pending advancement, already resolved out of content: the panel and the advisor read
    this and nothing else, so neither needs to reach into a pack."""

    prompt: str
    text: str = ""
    options: tuple[ContentRef, ...] = ()
    choose: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _choice_is_whole(self) -> Self:
        if self.choose > len(self.options):
            raise ValueError(f"cannot choose {self.choose} of {len(self.options)} options")
        return self


@dataclass(frozen=True, slots=True)
class ProposalSpec:
    """How one engine offers advancement and judges what the advisor proposes for it."""

    offered: Callable[[GameState], AdvancementOffer | None]
    instructions: str
    check: Callable[[GameState, AdvancementOffer, SheetDelta], str | None]

    def violation(self, state: GameState, offer: AdvancementOffer, delta: SheetDelta) -> str | None:
        """One legality rule for the advisor's retry and for the commit, so neither can drift:
        the picks are on offer, the delta leaves a valid sheet, and the engine's caps hold."""
        picked = [change.ref for change in delta.changes if isinstance(change, AddRef)]
        if outside := sorted(str(ref) for ref in picked if ref not in offer.options):
            allowed = ", ".join(str(ref) for ref in offer.options) or "(none)"
            return f"{', '.join(outside)} is not on offer here. The legal picks are: {allowed}"
        if len(picked) != offer.choose:
            return (
                f"this offer takes exactly {offer.choose} picks, the proposal makes {len(picked)}"
            )
        trial = player_sheet(state).model_copy(deep=True)
        try:
            _ = apply_delta(trial, delta)
            _ = Sheet.model_validate(trial.model_dump())
        except ValidationError as invalid:
            return f"the sheet this leaves is invalid: {invalid.errors()[0]['msg']}"
        except ValueError as refused:
            return str(refused)
        return self.check(state, offer, delta)


@dataclass(frozen=True, slots=True)
class Engine:
    id: EngineId
    initial_world: Callable[[AuthoredWorld, Rules], WorldState]
    validate_state: Callable[[GameState], None]
    default_rules: Callable[[Entity], Sheet]
    proposal: ProposalSpec
    toolsets: Mapping[str, AbstractToolset[object]]
    director_instructions: str
    entity_state: Callable[[Entity, Sheet], str]
    plan_type: type[TurnPlanBase]
    check_plan: PlanCheck
    resolve_action: ActionResolver


def narrator_evidence(facts: Sequence[Fact]) -> str:
    lines = [f"- {rendered}" for fact in facts if (rendered := fact.narrator) is not None]
    return "\n".join(lines) or NOTHING_MECHANICAL


def entity_renderer(engine: Engine, state: GameState) -> EntityRenderer:
    return lambda entity: engine.entity_state(entity, state.world.record(entity.id).rules)
