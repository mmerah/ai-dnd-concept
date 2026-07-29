from collections.abc import Callable, Sequence
from dataclasses import replace
from random import Random

from pydantic import Field

from .agents.context import Scene, TurnContext
from .agents.creator import create
from .agents.history import exchanges_to_messages
from .agents.prompting import (
    creator_prompt,
    director_prompt,
    maintainer_prompt,
    narrator_prompt,
)
from .agents.stages import DIRECTOR, MAINTAINER, NARRATOR
from .domain.models import (
    Entity,
    EntityCreated,
    EntityId,
    Exchange,
    GameState,
    GrowthRequest,
    LocationEntity,
    Role,
    Turn,
    updated,
)
from .domain.reducer import apply
from .engine.growth import screen
from .engine.resolve import resolve
from .engine.ruleset import Ruleset
from .utils.models import Frozen


class TurnOptions(Frozen):
    history_window: int = Field(ge=0)
    max_growth: int = Field(ge=0)


def _placement(request: GrowthRequest, scene: Scene) -> EntityId:
    if request.location is not None:
        wanted = request.location.casefold()
        for entity in scene.canon.values():
            if isinstance(entity, LocationEntity) and entity.name.casefold() == wanted:
                return entity.id
    return scene.where.id


async def _grow(
    context: TurnContext, requests: Sequence[GrowthRequest], prompts: dict[Role, str]
) -> tuple[list[Entity], GameState]:
    """Create locations first so later requests can refer to them."""
    created: list[Entity] = []
    for request in sorted(requests, key=lambda r: r.kind != "location"):
        scene = context.scene
        prompts["creator"] = creator_prompt(context, request)
        entity = await create(prompts["creator"], request, scene.canon, _placement(request, scene))
        created.append(entity)
        context = replace(context, state=apply(context.state, [EntityCreated(entity=entity)]))
    return created, context.state


async def run_turn(
    state: GameState,
    prompt: str,
    on_step: Callable[[Role], None] | None = None,
    *,
    ruleset: Ruleset,
    options: TurnOptions,
    rng: Random | None = None,
) -> Turn:
    step: Callable[[Role], None] = on_step or (lambda _: None)
    prompts: dict[Role, str] = {}

    recent = state.history[-options.history_window :]
    history = exchanges_to_messages(recent)

    context = TurnContext(state=state, prompt=prompt, rules=ruleset, recent=recent)
    step("director")
    prompts["director"] = director_prompt(context)
    direction = await DIRECTOR.run(prompts["director"], context.scene, history)

    events = resolve(direction.mechanics, state, rng or Random(), ruleset)
    draft = apply(state, events)

    context = replace(context, state=draft, events=events)
    step("narrator")
    prompts["narrator"] = narrator_prompt(context, direction)
    narration = await NARRATOR.run(prompts["narrator"], None, history)

    context = replace(context, narration=narration)
    step("maintainer")
    prompts["maintainer"] = maintainer_prompt(context)
    growth = await MAINTAINER.run(prompts["maintainer"], None, history)

    step("creator")
    screened = screen(growth.requests, draft.world.entities, options.max_growth)
    created, draft = await _grow(context, screened.accepted, prompts)

    return Turn(
        prompt=prompt,
        direction=direction,
        events=events,
        narration=narration,
        growth=growth,
        created=created,
        rejected=screened.rejected,
        state=updated(
            draft,
            history=[*draft.history, Exchange(prompt=prompt, narration=narration)],
            turn=draft.turn + 1,
        ),
        prompts=prompts,
    )
