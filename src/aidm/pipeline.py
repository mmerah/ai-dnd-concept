"""The fixed turn pipeline: DIRECTOR -> NARRATOR -> MAINTAINER -> CREATOR -> commit."""

from collections.abc import Callable
from dataclasses import replace
from random import Random

from pydantic_ai.messages import ModelMessage

from .agents.context import TurnContext, prompt_for, reads_history
from .agents.creator import create
from .agents.director import DirectorDeps, direct
from .agents.history import exchanges_to_messages
from .agents.maintainer import maintain
from .agents.narrator import narrate
from .config import settings
from .domain.events import EntityCreated, apply
from .domain.models import Direction, Entity, Exchange, GameState, Growth, Role, updated
from .domain.turn import Turn
from .engine.resolve import resolve


def _ignore(step: Role) -> None:
    """Default progress callback."""


async def _grow(context: TurnContext, growth: Growth, prompts: dict[Role, str]) -> list[Entity]:
    """The capped Maintainer -> Creator loop. Each creation feeds the next one's catalogue and
    dedup, so the local context evolves; only the created entities escape."""
    created: list[Entity] = []
    for request in growth.requests[: settings().max_growth]:
        taken = [e.id for e in context.state.world.entities]
        prompts["creator"] = prompt_for("creator", context, request=request)
        entity = await create(prompts["creator"], request, taken)
        created.append(entity)
        context = replace(context, state=apply(context.state, [EntityCreated(entity=entity)]))
    return created


async def run_turn(
    state: GameState,
    prompt: str,
    on_step: Callable[[Role], None] | None = None,
    *,
    rng: Random | None = None,
) -> Turn:
    """Run one full turn. Raises on any role failure, leaving `state` untouched. `rng` is injectable
    so the check outcome is deterministic under test; production leaves it defaulted."""
    step = on_step or _ignore
    prompts: dict[Role, str] = {}

    def ask(
        role: Role, context: TurnContext, *, direction: Direction | None = None
    ) -> str:
        step(role)
        prompts[role] = prompt_for(role, context, direction=direction)
        return prompts[role]

    history = exchanges_to_messages(state.history[-settings().history_window :])

    def seen_by(role: Role) -> list[ModelMessage] | None:
        return history if reads_history(role) else None

    context = TurnContext(state=state, prompt=prompt)
    deps = DirectorDeps(entities=state.world.entities)
    direction = await direct(ask("director", context), deps, seen_by("director"))

    events = resolve(direction.plan, state, rng or Random())
    draft = apply(state, events)

    context = replace(context, state=draft, events=events)
    narration = await narrate(ask("narrator", context, direction=direction), seen_by("narrator"))

    context = replace(context, narration=narration)
    growth = await maintain(ask("maintainer", context), seen_by("maintainer"))

    step("creator")
    created = await _grow(context, growth, prompts)
    draft = apply(draft, [EntityCreated(entity=entity) for entity in created])

    return Turn(
        prompt=prompt,
        direction=direction,
        events=events,
        narration=narration,
        growth=growth,
        created=created,
        state=_commit(draft, prompt, narration),
        prompts=prompts,
    )


def _commit(state: GameState, prompt: str, narration: str) -> GameState:
    return updated(
        state,
        history=[*state.history, Exchange(prompt=prompt, narration=narration)],
        turn=state.turn + 1,
    )
