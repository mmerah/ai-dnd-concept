from collections.abc import Callable, Sequence
from random import Random

from pydantic import Field

from .agents.context import (
    CreatorContext,
    DirectorContext,
    MaintainerContext,
    NarratorContext,
    build_catalogue_scene,
    build_director_scene,
    build_narrator_scene,
)
from .agents.history import exchanges_to_messages
from .agents.prompting import (
    build_creator_prompt,
    build_director_prompt,
    build_maintainer_prompt,
    build_narrator_prompt,
)
from .agents.stages import DirectorStage, SharedStages
from .domain.base import EntityId, Role, slug
from .domain.engine import require_engine
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
from .engines import Direction, Engine, record, resolve
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

    director_scene = build_director_scene(state)
    director_context = DirectorContext(
        scene=director_scene,
        scenario_title=state.scenario.title,
        scenario_premise=state.scenario.premise,
        prompt=prompt,
        recent=recent,
    )
    step("director")
    prompts["director"] = build_director_prompt(
        director_context,
        engine.presentation.entity_state,
    )
    direction: Direction = await director.run(prompts["director"], director_scene, history)

    events = resolve(engine, direction, state, rng)
    draft = apply(state, events, engine.rules)
    directed = record(engine, direction)
    evidence = narrator_evidence(events, engine.presentation.narrator_event)

    narrator_context = NarratorContext(
        scene=build_narrator_scene(draft, engine.presentation.entity_state),
        scenario_title=draft.scenario.title,
        scenario_premise=draft.scenario.premise,
        intent=directed.intent,
        tone=directed.tone,
        speaker_id=directed.speaker_id,
        evidence=evidence,
        prompt=prompt,
        recent=recent,
    )
    step("narrator")
    prompts["narrator"] = build_narrator_prompt(narrator_context)
    narration = await stages.narrator.run(prompts["narrator"], None, history)

    maintainer_context = MaintainerContext(
        scene=build_catalogue_scene(draft, engine.presentation.entity_state),
        scenario_title=draft.scenario.title,
        scenario_premise=draft.scenario.premise,
        prompt=prompt,
        evidence=evidence,
        narration=narration,
        recent=recent,
    )
    step("maintainer")
    prompts["maintainer"] = build_maintainer_prompt(maintainer_context)
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
        context = CreatorContext(
            scene=build_catalogue_scene(draft, engine.presentation.entity_state),
            scenario_title=draft.scenario.title,
            scenario_premise=draft.scenario.premise,
            narration=narration,
            recent=recent,
        )
        prompts["creator"] = build_creator_prompt(context, request)
        detail = await stages.creator.run(prompts["creator"], None)
        entity = _created_entity(
            request,
            detail,
            draft,
            _requested_location(request, draft),
        )
        rules = engine.lifecycle.rules_for_created_entity(entity, draft)
        if rules is not None:
            require_engine(rules, draft.engine, f"created entity {entity.id!r} rules")
        entity = updated(entity, rules=rules)
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
