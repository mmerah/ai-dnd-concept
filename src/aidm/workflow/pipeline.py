from collections.abc import Callable, Sequence
from dataclasses import dataclass
from random import Random

from pydantic import Field

from ..core.base import Entity, EntityDetail, EntityId, Frozen, Role, slug
from ..core.engine import entity_renderer, narrator_evidence
from ..core.facts import Fact
from ..core.registry import AnyEngine
from ..core.tools import TurnContext
from ..core.turn import GrowthRequest, Turn, screen_growth
from ..core.world import EngineRules, Exchange, GameState
from .agents import DirectorStage, SharedStages, exchanges_to_messages
from .prompts import (
    SceneSnapshot,
    VisibleScene,
    render_creator,
    render_director,
    render_maintainer,
    render_narrator,
)


class TurnOptions(Frozen):
    history_window: int = Field(ge=0)
    max_growth: int = Field(ge=0)


@dataclass(frozen=True, slots=True)
class TurnResult:
    """The committed state and the entry recording how it was reached, kept apart."""

    state: GameState[EngineRules]
    turn: Turn


async def run_turn(
    state: GameState[EngineRules],
    prompt: str,
    *,
    engine: AnyEngine,
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
    context = TurnContext(
        draft=state.draft(), rng=rng, facts=[], default_rules=engine.default_rules
    )
    notes = await director.run(prompts["director"], context, history)

    facts = tuple(context.facts)
    # Commit what the tools did before anyone reads it
    draft = context.draft.committed().draft()
    evidence = narrator_evidence(facts)

    after = SceneSnapshot.of(draft)
    describe = entity_renderer(engine, draft)
    step("narrator")
    prompts["narrator"] = render_narrator(
        VisibleScene.of(after),
        describe,
        draft.scenario,
        intent=notes.intent,
        tone=notes.tone,
        speaker_id=notes.speaker_id,
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
            notes=notes,
            facts=(*facts, *creation_facts),
            narrator_evidence=evidence,
            narration=narration,
            growth=growth,
            created=created,
            rejected=screened.rejected,
            prompts=prompts,
        ),
    )


async def _grow(
    draft: GameState[EngineRules],
    requests: Sequence[GrowthRequest],
    narration: str,
    recent: tuple[Exchange, ...],
    prompts: dict[Role, str],
    stages: SharedStages,
    engine: AnyEngine,
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
        entity = _created_entity(request, detail, draft)
        facts.append(draft.add(entity, engine.default_rules(entity)))
        created.append(entity)
    return tuple(created), tuple(facts)


def _created_entity(
    request: GrowthRequest, detail: EntityDetail, state: GameState[EngineRules]
) -> Entity:
    return Entity(
        id=slug(request.name, state.world.all_ids()),
        kind=request.kind,
        name=request.name,
        brief=request.brief,
        detail=detail,
        known=True,
        parent_id=None if request.kind == "location" else _requested_location(request, state),
    )


def _requested_location(request: GrowthRequest, state: GameState[EngineRules]) -> EntityId:
    if request.location is not None:
        wanted = request.location.casefold()
        for entity in state.world.entities("location"):
            if entity.name.casefold() == wanted:
                return entity.id
    return state.player_location


def _ignore_step(role: Role) -> None:
    del role
