from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from random import Random
from types import NoneType

from pydantic import Field
from pydantic_ai import ModelRetry, NativeOutput, RunContext, ToolOutput
from pydantic_ai.messages import ModelMessage

from ..core.base import Entity, EntityDetail, EntityId, Frozen, slug
from ..core.config import Settings
from ..core.effects import apply_effect
from ..core.engine import entity_renderer, narrator_evidence
from ..core.facts import Fact
from ..core.plan import TurnPlanBase
from ..core.registry import AnyEngine
from ..core.turn import Growth, GrowthRequest, RejectedGrowth, Turn, screen_growth
from ..core.world import EngineRules, Exchange, GameState
from . import prompts
from .prompts import SceneSnapshot, VisibleScene
from .roles import Stage, exchanges_to_messages, stage


class TurnOptions(Frozen):
    history_window: int = Field(ge=0)
    max_growth: int = Field(ge=0)


@dataclass(frozen=True, slots=True)
class TurnResult:
    """The committed state and the entry recording how it was reached, kept apart."""

    state: GameState[EngineRules]
    turn: Turn


@dataclass(frozen=True, slots=True)
class PlanContext:
    """What the Director's output validator judges a plan against: the untouched committed state."""

    engine: AnyEngine
    state: GameState[EngineRules]


@dataclass
class TurnWorkspace:
    prompt: str
    history: list[ModelMessage]
    state: GameState[EngineRules]
    draft: GameState[EngineRules]
    rng: Random
    recent: tuple[Exchange, ...]
    facts: list[Fact] = field(default_factory=list)
    prompts: dict[str, str] = field(default_factory=dict)
    plan: TurnPlanBase | None = None
    evidence: str = ""
    narration: str = ""
    growth: Growth | None = None
    accepted: tuple[GrowthRequest, ...] = ()
    rejected: tuple[RejectedGrowth, ...] = ()
    created: tuple[Entity, ...] = ()

    def settled(self) -> TurnPlanBase:
        if self.plan is None:
            raise ValueError("this step ran before a director step settled the plan")
        return self.plan


type StepFn = Callable[[TurnWorkspace], Awaitable[None]]
type TurnScript = tuple[tuple[str, StepFn], ...]


def director_step(role: Stage[PlanContext, TurnPlanBase], engine: AnyEngine) -> StepFn:
    async def run(ws: TurnWorkspace) -> None:
        state = ws.state
        ws.prompts[role.name] = prompts.render_director(
            SceneSnapshot.of(state), entity_renderer(engine, state), state.scenario, ws.prompt
        )
        ws.plan = await role.run(
            ws.prompts[role.name], PlanContext(engine=engine, state=state), ws.history
        )

    return run


def resolve_step(engine: AnyEngine) -> StepFn:
    """Pure code: the action's procedure on the draft, then the plan's unconditional effects."""

    async def run(ws: TurnWorkspace) -> None:
        plan = ws.settled()
        ws.facts.extend(engine.resolve_action(ws.draft, plan, ws.rng))
        for effect in plan.effects:
            ws.facts.extend(apply_effect(ws.draft, effect, engine.default_rules))
        ws.draft = ws.draft.committed().draft()
        ws.evidence = narrator_evidence(ws.facts)

    return run


def narrator_step(role: Stage[None, str], engine: AnyEngine) -> StepFn:
    async def run(ws: TurnWorkspace) -> None:
        plan = ws.settled()
        draft = ws.draft
        ws.prompts[role.name] = prompts.render_narrator(
            VisibleScene.of(SceneSnapshot.of(draft)),
            entity_renderer(engine, draft),
            draft.scenario,
            intent=plan.intent,
            tone=plan.tone,
            speaker_id=plan.speaker_id,
            evidence=ws.evidence,
            prompt=ws.prompt,
        )
        ws.narration = await role.run(ws.prompts[role.name], None, ws.history)

    return run


def maintainer_step(role: Stage[None, Growth], engine: AnyEngine, options: TurnOptions) -> StepFn:
    async def run(ws: TurnWorkspace) -> None:
        draft = ws.draft
        ws.prompts[role.name] = prompts.render_maintainer(
            SceneSnapshot.of(draft),
            entity_renderer(engine, draft),
            draft.scenario,
            prompt=ws.prompt,
            evidence=ws.evidence,
            narration=ws.narration,
        )
        growth = await role.run(ws.prompts[role.name], None, ws.history)
        screened = screen_growth(
            growth.requests, {entity.name for entity in draft.world.entities()}, options.max_growth
        )
        ws.growth = growth
        ws.accepted, ws.rejected = screened.accepted, screened.rejected

    return run


def creator_step(role: Stage[None, EntityDetail], engine: AnyEngine) -> StepFn:
    async def run(ws: TurnWorkspace) -> None:
        draft = ws.draft
        for request in sorted(ws.accepted, key=lambda item: item.kind != "location"):
            ws.prompts[role.name] = prompts.render_creator(
                SceneSnapshot.of(draft),
                entity_renderer(engine, draft),
                draft.scenario,
                narration=ws.narration,
                recent=ws.recent,
                request=request,
            )
            detail = await role.run(ws.prompts[role.name], None)
            entity = _created_entity(request, detail, draft)
            ws.facts.append(draft.add(entity, engine.default_rules(entity)))
            ws.created = (*ws.created, entity)

    return run


@dataclass(frozen=True, slots=True)
class Cast:
    director: Stage[PlanContext, TurnPlanBase]
    narrator: Stage[None, str]
    maintainer: Stage[None, Growth]
    creator: Stage[None, EntityDetail]

    def script(self, engine: AnyEngine, options: TurnOptions) -> TurnScript:
        return (
            (self.director.name, director_step(self.director, engine)),
            ("resolve", resolve_step(engine)),
            (self.narrator.name, narrator_step(self.narrator, engine)),
            (self.maintainer.name, maintainer_step(self.maintainer, engine, options)),
            (self.creator.name, creator_step(self.creator, engine)),
        )


def director_stage(engine: AnyEngine, settings: Settings) -> Stage[PlanContext, TurnPlanBase]:
    built = stage(
        "director",
        settings,
        instructions=f"{prompts.CORE_DIRECTOR}\n\n{engine.director_instructions}",
        output_type=ToolOutput(engine.plan_type, name="turn_plan"),
        deps_type=PlanContext,
        toolsets=(engine.toolsets["director"],),
    )

    def legal(ctx: RunContext[PlanContext], plan: TurnPlanBase) -> TurnPlanBase:
        deps = ctx.deps
        refused = deps.engine.check_plan(deps.state, plan)
        if refused is not None:
            raise ModelRetry(refused)
        return plan

    _ = built.agent.output_validator(legal)
    return built


def default_cast(engine: AnyEngine, settings: Settings) -> Cast:
    return Cast(
        director=director_stage(engine, settings),
        narrator=stage(
            "narrator", settings, instructions=prompts.NARRATOR, output_type=str, deps_type=NoneType
        ),
        maintainer=stage(
            "maintainer",
            settings,
            instructions=prompts.MAINTAINER,
            output_type=NativeOutput(Growth),
            deps_type=NoneType,
        ),
        creator=stage(
            "creator",
            settings,
            instructions=prompts.CREATOR,
            output_type=NativeOutput(EntityDetail),
            deps_type=NoneType,
        ),
    )


async def run_turn(
    state: GameState[EngineRules],
    prompt: str,
    *,
    engine: AnyEngine,
    script: TurnScript,
    options: TurnOptions,
    rng: Random,
    on_step: Callable[[str], None] | None = None,
) -> TurnResult:
    recent = state.history[-options.history_window :]
    ws = TurnWorkspace(
        prompt=prompt,
        history=exchanges_to_messages(recent),
        state=state,
        draft=state.draft(),
        rng=rng,
        recent=recent,
    )
    for name, step in script:
        if on_step is not None:
            on_step(name)
        await step(ws)
    plan = ws.plan
    if plan is None:
        raise ValueError("script finished without a turn plan")
    if not ws.narration:
        raise ValueError("script finished without a narration")
    if ws.growth is None:
        raise ValueError("script finished without growth")
    if len(ws.created) < len(ws.accepted):
        raise ValueError("script finished with accepted growth requests uncreated")
    draft = ws.draft
    draft.history = (*draft.history, Exchange(prompt=prompt, narration=ws.narration))
    draft.turn += 1
    final = draft.committed()
    engine.validate_state(final)
    return TurnResult(
        state=final,
        turn=Turn(
            prompt=prompt,
            plan=plan.model_dump(mode="json"),
            facts=tuple(ws.facts),
            narrator_evidence=ws.evidence,
            narration=ws.narration,
            growth=ws.growth,
            created=ws.created,
            rejected=ws.rejected,
            prompts=ws.prompts,
        ),
    )


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
