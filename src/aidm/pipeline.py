from collections.abc import Callable, Sequence
from random import Random

from pydantic import Field

from .agents.context import SceneSnapshot, VisibleScene
from .agents.history import exchanges_to_messages
from .agents.prompting import (
    render_creator,
    render_director,
    render_maintainer,
    render_narrator,
)
from .agents.stages import DirectorStage, SharedStages
from .domain.base import EntityId, Role, slug
from .domain.entities import (
    ActorEntity,
    Entity,
    EntityDetail,
    ItemEntity,
    LocationEntity,
    placement,
)
from .domain.events import EntityCreated, Event
from .domain.growth import GrowthRequest, screen_growth
from .domain.reducer import apply, narrator_evidence
from .domain.state import Exchange, GameState
from .domain.turn import Turn
from .engines import Direction, Engine, entity_renderer, record, resolve
from .utils.models import Frozen, updated


class TurnOptions(Frozen):
    history_window: int = Field(ge=0)
    max_growth: int = Field(ge=0)


async def run_turn(
    state: GameState,
    prompt: str,
    *,
    engine: Engine,
    director: DirectorStage,
    stages: SharedStages,
    options: TurnOptions,
    rng: Random,
    on_step: Callable[[Role], None] | None = None,
) -> Turn:
    step = on_step or _ignore_step
    prompts: dict[Role, str] = {}
    recent = state.history[-options.history_window :]
    history = exchanges_to_messages(recent)

    step("director")
    prompts["director"] = render_director(
        SceneSnapshot.of(state),
        entity_renderer(engine, state),
        state.scenario,
        prompt,
    )
    direction: Direction = await director.run(prompts["director"], state, history)

    events = resolve(engine, direction, state, rng)
    draft = apply(state, events, engine.rules)
    directed = record(engine, direction)
    evidence = narrator_evidence(events, engine.presentation.narrator_event)

    after = SceneSnapshot.of(draft)
    describe = entity_renderer(engine, draft)
    step("narrator")
    prompts["narrator"] = render_narrator(
        VisibleScene.of(after),
        describe,
        draft.scenario,
        intent=directed.intent,
        tone=directed.tone,
        speaker_id=directed.speaker_id,
        evidence=evidence,
        prompt=prompt,
    )
    narration = await stages.narrator.run(prompts["narrator"], None, history)

    step("maintainer")
    prompts["maintainer"] = render_maintainer(
        after,
        describe,
        draft.scenario,
        prompt=prompt,
        evidence=evidence,
        narration=narration,
    )
    growth = await stages.maintainer.run(prompts["maintainer"], None, history)
    screened = screen_growth(
        growth.requests,
        {entity.name for entity in draft.world.entities.values()},
        options.max_growth,
    )

    step("creator")
    created, creation_events, draft = await _grow(
        draft,
        screened.accepted,
        narration,
        recent,
        prompts,
        stages,
        engine,
    )
    final = updated(
        draft,
        history=(*draft.history, Exchange(prompt=prompt, narration=narration)),
        turn=draft.turn + 1,
    )
    engine.rules.validate_state(final)
    return Turn(
        prompt=prompt,
        direction=directed,
        events=(*events, *creation_events),
        narrator_evidence=evidence,
        narration=narration,
        growth=growth,
        created=created,
        rejected=screened.rejected,
        state=final,
        prompts=prompts,
    )


async def _grow(
    state: GameState,
    requests: Sequence[GrowthRequest],
    narration: str,
    recent: tuple[Exchange, ...],
    prompts: dict[Role, str],
    stages: SharedStages,
    engine: Engine,
) -> tuple[tuple[Entity, ...], tuple[Event, ...], GameState]:
    created: list[Entity] = []
    events: list[Event] = []
    draft = state
    for request in sorted(requests, key=lambda item: item.kind != "location"):
        prompts["creator"] = render_creator(
            SceneSnapshot.of(draft),
            entity_renderer(engine, draft),
            draft.scenario,
            narration=narration,
            recent=recent,
            request=request,
        )
        detail = await stages.creator.run(prompts["creator"], None)
        entity = _created_entity(
            request,
            detail,
            draft,
            _requested_location(request, draft),
        )
        event = EntityCreated(entity=entity)
        draft = apply(draft, [event], engine.rules)
        created.append(entity)
        events.append(event)
    return tuple(created), tuple(events), draft


def _created_entity(
    request: GrowthRequest,
    detail: EntityDetail,
    state: GameState,
    location: EntityId,
) -> Entity:
    entity_id = slug(request.name, state.world.entities)
    fields = {
        "id": entity_id,
        "name": request.name,
        "brief": request.brief,
        "detail": detail,
        "known": True,
        "authored": False,
    } | placement(request.kind, location)
    match request.kind:
        case "actor":
            return ActorEntity.model_validate(fields)
        case "item":
            return ItemEntity.model_validate(fields)
        case "location":
            return LocationEntity.model_validate(fields)


def _requested_location(request: GrowthRequest, state: GameState) -> EntityId:
    if request.location is not None:
        wanted = request.location.casefold()
        for entity in state.world.entities.values():
            if isinstance(entity, LocationEntity) and entity.name.casefold() == wanted:
                return entity.id
    return state.player.location_id


def _ignore_step(role: Role) -> None:
    del role
