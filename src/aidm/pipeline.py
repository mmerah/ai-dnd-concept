"""The fixed turn pipeline: DIRECTOR -> NARRATOR -> MAINTAINER -> CREATOR -> commit."""

from collections.abc import Callable, Sequence
from dataclasses import replace
from random import Random

from pydantic import Field
from pydantic_ai.messages import ModelMessage

from .agents.context import Scene, TurnContext
from .agents.creator import create
from .agents.director import direct
from .agents.history import exchanges_to_messages
from .agents.maintainer import maintain
from .agents.narrator import narrate
from .agents.prompting import (
    NATIVE_HISTORY,
    creator_prompt,
    director_prompt,
    maintainer_prompt,
    narrator_prompt,
)
from .content import Library
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
    """How much past a turn is shown and how much canon it may grow. Handed in rather than read from
    config here, so the pipeline has no global left to reach for."""

    history_window: int = Field(ge=0)
    max_growth: int = Field(ge=0)


def _placement(request: GrowthRequest, scene: Scene) -> EntityId:
    """Where a grown actor/item stands: the location it names, matched to a canon location by name
    (existing or just created this batch), else the player's location. A grown location needs none;
    the id passed then is ignored by the Creator."""
    if request.location is not None:
        wanted = request.location.casefold()
        for entity in scene.canon.values():
            if isinstance(entity, LocationEntity) and entity.name.casefold() == wanted:
                return entity.id
    return scene.where.id


async def _grow(
    context: TurnContext, requests: Sequence[GrowthRequest], prompts: dict[Role, str]
) -> tuple[list[Entity], GameState]:
    """The Maintainer -> Creator loop over screened requests. Locations are created first, so an
    actor/item can name a location this same batch mints and be placed there; each creation feeds
    the next one's catalogue and dedup, so only the created entities and the state they were folded
    into escape."""
    created: list[Entity] = []
    for request in sorted(requests, key=lambda r: r.kind != "location"):
        scene = context.scene
        prompts["creator"] = creator_prompt(context, request)
        entity = await create(
            prompts["creator"], request, scene.canon, _placement(request, scene)
        )
        created.append(entity)
        context = replace(context, state=apply(context.state, [EntityCreated(entity=entity)]))
    return created, context.state


async def run_turn(
    state: GameState,
    prompt: str,
    on_step: Callable[[Role], None] | None = None,
    *,
    library: Library,
    ruleset: Ruleset,
    options: TurnOptions,
    rng: Random | None = None,
) -> Turn:
    """Run one full turn. Raises on any role failure, leaving `state` untouched. `rng` is injectable
    so the check outcome is deterministic under test; production leaves it defaulted.

    Both content handles are passed until the Narrator's and Director's views read profiles too: the
    engine resolves against `ruleset`, and `views` still renders records out of `library`."""
    step: Callable[[Role], None] = on_step or (lambda _: None)
    prompts: dict[Role, str] = {}

    recent = state.history[-options.history_window :]
    history = exchanges_to_messages(recent)

    def seen_by(role: Role) -> list[ModelMessage] | None:
        return history if role in NATIVE_HISTORY else None

    context = TurnContext(state=state, prompt=prompt, library=library, recent=recent)
    step("director")
    prompts["director"] = director_prompt(context)
    direction = await direct(prompts["director"], context.scene, seen_by("director"))

    events = resolve(direction.mechanics, state, rng or Random(), ruleset)
    draft = apply(state, events)

    context = replace(context, state=draft, events=events)
    step("narrator")
    prompts["narrator"] = narrator_prompt(context, direction)
    narration = await narrate(prompts["narrator"], seen_by("narrator"))

    context = replace(context, narration=narration)
    step("maintainer")
    prompts["maintainer"] = maintainer_prompt(context)
    growth = await maintain(prompts["maintainer"], seen_by("maintainer"))

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
