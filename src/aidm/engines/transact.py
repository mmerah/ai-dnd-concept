from collections.abc import Callable, Sequence
from random import Random

from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.tools import ToolFuncEither
from pydantic_ai.toolsets import FunctionToolset

from aidm.state.base import EntityId
from aidm.state.facts import Fact
from aidm.state.world import Game, check_draft

from .engine import Engine, PlanContext
from .sheets import SheetBase

NOTHING_CHANGED = "- (nothing changed)"

# The rng is a parameter so a trial run against a throwaway copy cannot consume the turn's dice.
type Play = Callable[[Game, Random], tuple[Fact, ...]]


def apply_to_draft(
    engine: Engine[SheetBase], draft: Game, play: Play, rng: Random
) -> tuple[Fact, ...]:
    """Every mutation runs this sequence, so seeding cannot be forgotten by a caller."""
    landed = play(draft, rng)
    _seed_created(engine, draft, landed, rng)
    engine.validate(draft)
    return landed


def transact(
    engine: Engine[SheetBase], draft: Game, play: Play, rng: Random
) -> tuple[Game, tuple[Fact, ...]]:
    """A draft mutated and committed whole, for a change that stands on its own outside a turn."""
    landed = apply_to_draft(engine, draft, play, rng)
    return draft.committed(), landed


def act(ctx: RunContext[PlanContext], play: Play) -> str:
    """Refused against a throwaway copy, applied to the turn's draft, answered with what changed."""
    deps = ctx.deps
    if refused := check_draft(
        deps.state, lambda copy: apply_to_draft(deps.engine, copy, play, Random(0))
    ):
        raise ModelRetry(refused)
    already_pending = len(deps.state.world.pending_notes)
    landed = apply_to_draft(deps.engine, deps.state, play, deps.rng)
    deps.log.facts.extend(landed)
    lines = [f"- {fact.trace}" for fact in landed]
    lines.extend(f"- {note}" for note in deps.state.world.pending_notes[already_pending:])
    lines.extend(_reached(deps.state, landed))
    return "\n".join(lines) or NOTHING_CHANGED


def sequential_toolset(
    tools: list[ToolFuncEither[PlanContext, ...]],
) -> FunctionToolset[PlanContext]:
    """One tool at a time: two calls in one answer would interleave on the same draft."""
    return FunctionToolset(
        tools=tools, sequential=True, require_parameter_descriptions=True, max_retries=2
    )


def _seed_created(
    engine: Engine[SheetBase], draft: Game, facts: Sequence[Fact], rng: Random
) -> None:
    for fact in facts:
        created = fact.data.get("entity_id") if fact.kind == "entity_created" else None
        if isinstance(created, str):
            engine.seed(draft, draft.world.require(EntityId(created)), rng)


def _reached(draft: Game, facts: Sequence[Fact]) -> list[str]:
    # The prompt was rendered before the discovery, so the instruction authored for it arrives here.
    lines: list[str] = []
    for fact in facts:
        found = fact.data.get("entity_id") if fact.kind == "entity_discovered" else None
        if not isinstance(found, str):
            continue
        detail = draft.world.require(EntityId(found)).detail
        if detail is not None and detail.when_reached:
            lines.append(f"- {detail.when_reached}")
    return lines
