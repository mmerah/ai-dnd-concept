"""The fixed turn pipeline: DIRECTOR -> ACTOR -> NARRATOR -> MAINTAINER -> CREATOR -> commit."""

from collections.abc import Callable
from dataclasses import replace
from random import Random

from .agents.actor import ActorDeps, act
from .agents.context import TurnContext, prompt_for
from .agents.creator import create
from .agents.director import direct
from .agents.maintainer import maintain
from .agents.narrator import narrate
from .config import settings
from .domain.events import EntityCreated, apply
from .domain.models import Entity, Exchange, GameState, Role, updated
from .domain.turn import Turn


def _ignore(step: Role) -> None:
    """Default progress callback."""


async def run_turn(
    state: GameState, prompt: str, on_step: Callable[[Role], None] | None = None
) -> Turn:
    """Run one full turn. Raises on any role failure, leaving `state` untouched."""
    step = on_step or _ignore
    prompts: dict[Role, str] = {}

    def ask(role: Role, context: TurnContext) -> str:
        step(role)
        prompts[role] = prompt_for(role, context)
        return prompts[role]

    context = TurnContext(state=state, prompt=prompt)
    direction = await direct(ask("director", context))

    context = replace(context, direction=direction)
    deps = ActorDeps(state=state, rng=Random())
    events, report = await act(ask("actor", context), deps)
    draft = apply(state, events)

    context = replace(context, state=draft, events=events)
    narration = await narrate(ask("narrator", context))

    context = replace(context, narration=narration)
    growth = await maintain(ask("maintainer", context))

    step("creator")
    created: list[Entity] = []
    for request in growth.requests[: settings().max_growth]:
        context = replace(context, request=request)
        taken = [e.id for e in context.state.scenario.entities]
        prompts["creator"] = prompt_for("creator", context)  # last request wins in the trace
        entity = await create(prompts["creator"], request, taken)
        created.append(entity)
        draft = apply(draft, [EntityCreated(entity=entity)])
        context = replace(context, state=draft)

    return Turn(
        prompt=prompt,
        direction=direction,
        events=events,
        report=report,
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
