"""The fixed turn pipeline: DIRECTOR -> NARRATOR -> MAINTAINER -> CREATOR -> commit."""

from collections.abc import Callable, Sequence
from dataclasses import replace
from random import Random

from pydantic_ai.messages import ModelMessage

from .agents.context import TurnContext
from .agents.creator import create
from .agents.director import DirectorDeps, direct
from .agents.history import exchanges_to_messages
from .agents.maintainer import maintain
from .agents.narrator import narrate
from .agents.policy import prompt_for, reads_history
from .config import settings
from .domain.models import (
    Direction,
    Entity,
    EntityCreated,
    Exchange,
    GameState,
    GrowthRequest,
    Role,
    Turn,
    updated,
)
from .domain.reducer import apply
from .engine.growth import screen
from .engine.resolve import resolve


def _ignore(step: Role) -> None:
    """Default progress callback."""


async def _grow(
    context: TurnContext, requests: Sequence[GrowthRequest], prompts: dict[Role, str]
) -> list[Entity]:
    """The Maintainer -> Creator loop over screened requests. Each creation feeds the next one's
    catalogue and dedup, so the local context evolves; only the created entities escape."""
    created: list[Entity] = []
    for request in requests:
        taken = context.state.world.entities.keys()
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

    def ask(role: Role, context: TurnContext, *, direction: Direction | None = None) -> str:
        step(role)
        prompts[role] = prompt_for(role, context, direction=direction)
        return prompts[role]

    recent = state.history[-settings().history_window :]
    history = exchanges_to_messages(recent)

    def seen_by(role: Role) -> list[ModelMessage] | None:
        return history if reads_history(role) else None

    context = TurnContext(state=state, prompt=prompt, recent=recent)
    deps = DirectorDeps(entities=state.world.entities)
    direction = await direct(ask("director", context), deps, seen_by("director"))

    events = resolve(direction.mechanics, state, rng or Random())
    draft = apply(state, events)

    context = replace(context, state=draft, events=events)
    narration = await narrate(ask("narrator", context, direction=direction), seen_by("narrator"))

    context = replace(context, narration=narration)
    growth = await maintain(ask("maintainer", context), seen_by("maintainer"))

    step("creator")
    screened = screen(growth.requests, draft.world.entities, settings().max_growth)
    created = await _grow(context, screened.accepted, prompts)
    draft = apply(draft, [EntityCreated(entity=entity) for entity in created])

    return Turn(
        prompt=prompt,
        direction=direction,
        events=events,
        narration=narration,
        growth=growth,
        created=created,
        rejected=screened.rejected,
        state=_commit(draft, prompt, narration),
        prompts=prompts,
    )


def _commit(state: GameState, prompt: str, narration: str) -> GameState:
    return updated(
        state,
        history=[*state.history, Exchange(prompt=prompt, narration=narration)],
        turn=state.turn + 1,
    )
