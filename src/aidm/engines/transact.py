from collections.abc import Callable, Sequence
from dataclasses import dataclass
from random import Random

from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.tools import ToolFuncEither
from pydantic_ai.toolsets import FunctionToolset

from aidm.state.base import EntityId
from aidm.state.facts import Fact
from aidm.state.hooks import fire_hooks
from aidm.state.resolution import Resolution, check_draft
from aidm.state.world import GameState

from .engine import Engine, PlanContext
from .sheets import SheetBase

NOTHING_CHANGED = "- (nothing changed)"

# The rng is a parameter so a trial run against a throwaway copy cannot consume the turn's dice.
type Play = Callable[[GameState, Random], Resolution]


@dataclass(frozen=True, slots=True)
class Resolved:
    """One mutation of a draft: the facts resolved, and the facts hooks fired in reaction."""

    resolved: tuple[Fact, ...]
    fired: tuple[Fact, ...]

    @property
    def facts(self) -> tuple[Fact, ...]:
        return (*self.resolved, *self.fired)


def apply_to_draft(
    engine: Engine[SheetBase], draft: GameState, play: Play, rng: Random
) -> Resolved:
    """Every mutation runs this sequence, so hooks and seeding cannot be forgotten by a caller."""
    resolution = play(draft, rng)
    fired = fire_hooks(draft, resolution.facts)
    _seed_created(engine, draft, [*resolution.facts, *fired], rng)
    engine.validate(draft)
    # Written back here, not at commit: a later tool takes trial copies of this same draft, and an
    # unflushed mechanics mutation would be missing from every one of them.
    draft.flush_mechanics()
    return Resolved(resolved=resolution.facts, fired=tuple(fired))


def transact(
    engine: Engine[SheetBase], draft: GameState, play: Play, rng: Random
) -> tuple[GameState, tuple[Fact, ...]]:
    """A draft mutated and committed whole, for a change that stands on its own outside a turn."""
    landed = apply_to_draft(engine, draft, play, rng)
    return draft.committed(), landed.facts


def act(ctx: RunContext[PlanContext], play: Play) -> str:
    """Refused against a throwaway copy, applied to the turn's draft, answered with what changed."""
    deps = ctx.deps
    if refused := check_draft(
        deps.state, lambda copy: apply_to_draft(deps.engine, copy, play, Random(0))
    ):
        raise ModelRetry(refused)
    already_pending = len(deps.state.world.pending_notes)
    landed = apply_to_draft(deps.engine, deps.state, play, deps.rng)
    deps.log.facts.extend(landed.facts)
    deps.log.fired.extend(landed.fired)
    lines = [f"- {fact.trace}" for fact in landed.facts]
    lines.extend(f"- {note}" for note in deps.state.world.pending_notes[already_pending:])
    return "\n".join(lines) or NOTHING_CHANGED


def sequential_toolset(
    tools: list[ToolFuncEither[PlanContext, ...]],
) -> FunctionToolset[PlanContext]:
    """One tool at a time: two calls in one answer would interleave on the same draft."""
    return FunctionToolset(
        tools=tools, sequential=True, require_parameter_descriptions=True, max_retries=2
    )


def _seed_created(
    engine: Engine[SheetBase], draft: GameState, facts: Sequence[Fact], rng: Random
) -> None:
    for fact in facts:
        created = fact.data.get("entity_id") if fact.kind == "entity_created" else None
        if isinstance(created, str):
            engine.seed(draft, draft.world.require(EntityId(created)), rng)
