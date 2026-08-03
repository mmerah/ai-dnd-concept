from collections.abc import Callable, Sequence
from dataclasses import dataclass
from random import Random

from pydantic import Field

from .agents import DirectorStage, SharedStages, exchanges_to_messages
from .base import (
    ActorEntity,
    Entity,
    EntityDetail,
    EntityId,
    Frozen,
    ItemEntity,
    LocationEntity,
    Role,
    slug,
)
from .engine import Engine, entity_renderer, narrator_evidence
from .facts import Fact
from .growth import GrowthRequest, screen_growth
from .prompts import (
    SceneSnapshot,
    VisibleScene,
    render_creator,
    render_director,
    render_maintainer,
    render_narrator,
)
from .transition import Direction
from .turn import Turn
from .world import Exchange, GameState


class TurnOptions(Frozen):
    history_window: int = Field(ge=0)
    max_growth: int = Field(ge=0)


@dataclass(frozen=True, slots=True)
class TurnResult:
    """The committed state and the entry recording how it was reached, kept apart."""

    state: GameState
    turn: Turn


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
) -> TurnResult:
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

    transition = engine.resolve(direction, state, rng)
    draft = transition.state.draft()
    evidence = narrator_evidence(transition.facts)

    after = SceneSnapshot.of(draft)
    describe = entity_renderer(engine, draft)
    step("narrator")
    prompts["narrator"] = render_narrator(
        VisibleScene.of(after),
        describe,
        draft.scenario,
        intent=direction.intent,
        tone=direction.tone,
        speaker_id=direction.speaker_id,
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
        {entity.name for entity in draft.world.entities()},
        options.max_growth,
    )

    step("creator")
    created, creation_facts = await _grow(
        draft,
        screened.accepted,
        narration,
        recent,
        prompts,
        stages,
        engine,
    )
    draft.history = (*draft.history, Exchange(prompt=prompt, narration=narration))
    draft.turn += 1
    final = draft.committed()
    engine.validate_state(final)
    return TurnResult(
        state=final,
        turn=Turn(
            prompt=prompt,
            direction=direction,
            facts=(*transition.facts, *creation_facts),
            narrator_evidence=evidence,
            narration=narration,
            growth=growth,
            created=created,
            rejected=screened.rejected,
            prompts=prompts,
        ),
    )


async def _grow(
    draft: GameState,
    requests: Sequence[GrowthRequest],
    narration: str,
    recent: tuple[Exchange, ...],
    prompts: dict[Role, str],
    stages: SharedStages,
    engine: Engine,
) -> tuple[tuple[Entity, ...], tuple[Fact, ...]]:
    created: list[Entity] = []
    facts: list[Fact] = []
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
        facts.append(draft.add(entity, engine.default_rules(entity)))
        created.append(entity)
    return tuple(created), tuple(facts)


def _created_entity(
    request: GrowthRequest,
    detail: EntityDetail,
    state: GameState,
    location: EntityId,
) -> Entity:
    entity_id = slug(request.name, state.world.all_ids())
    fields = {
        "id": entity_id,
        "name": request.name,
        "brief": request.brief,
        "detail": detail,
        "known": True,
    }
    match request.kind:
        case "actor":
            return ActorEntity.model_validate(fields | {"location_id": location})
        case "item":
            return ItemEntity.model_validate(fields | {"container_id": location})
        case "location":
            return LocationEntity.model_validate(fields)


def _requested_location(request: GrowthRequest, state: GameState) -> EntityId:
    if request.location is not None:
        wanted = request.location.casefold()
        for entity in state.world.locations.values():
            if entity.name.casefold() == wanted:
                return entity.id
    return state.player.location_id


def _ignore_step(role: Role) -> None:
    del role
