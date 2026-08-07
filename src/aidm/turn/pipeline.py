from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from random import Random
from types import NoneType

from pydantic import Field, ValidationError
from pydantic_ai import ModelRetry, NativeOutput, RunContext, TextOutput, ToolOutput
from pydantic_ai.messages import ModelMessage

from aidm.config import Settings
from aidm.engines.loader import Engine
from aidm.state.apply import apply_effect, fire_hooks
from aidm.state.base import Entity, EntityId, Frozen, slug
from aidm.state.facts import Fact, narrator_evidence
from aidm.state.plan import TurnPlanBase, check_speaker
from aidm.state.turn import Creation, SceneDirective, StepTrace, Turn, WorldkeeperReport
from aidm.state.world import Exchange, GameState

from . import prompts
from .prompts import SceneSnapshot, VisibleScene
from .roles import Stage, exchanges_to_messages, stage


class TurnOptions(Frozen):
    history_window: int = Field(ge=0)
    max_growth: int = Field(ge=0)


@dataclass(frozen=True, slots=True)
class TurnResult:
    """The committed state and the entry recording how it was reached, kept apart."""

    state: GameState
    turn: Turn


@dataclass(frozen=True, slots=True)
class PlanContext:
    """What the Director's output validator judges a plan against: the untouched committed state."""

    engine: Engine
    state: GameState


@dataclass
class TurnWorkspace:
    prompt: str
    history: list[ModelMessage]
    state: GameState
    draft: GameState
    rng: Random
    facts: list[Fact] = field(default_factory=list)
    steps: list[StepTrace] = field(default_factory=list)
    plan: TurnPlanBase | None = None
    directive: SceneDirective | None = None
    evidence: str = ""
    narration: str = ""

    def settled(self) -> TurnPlanBase:
        if self.plan is None:
            raise ValueError("this step ran before a director step settled the plan")
        return self.plan

    def briefed(self) -> SceneDirective:
        if self.directive is None:
            raise ValueError("this step ran before a scene step settled the directive")
        return self.directive


type StepFn = Callable[[TurnWorkspace], Awaitable[None]]
type TurnScript = tuple[tuple[str, StepFn], ...]


def scene_step(role: Stage[GameState, SceneDirective], engine: Engine) -> StepFn:
    """The Scene Director reads the full view and hands the Rules Director a directive."""

    async def run(ws: TurnWorkspace) -> None:
        state = ws.state
        rendered = prompts.render_director(
            SceneSnapshot.of(state), engine.renderer(state), state.scenario, ws.prompt
        )
        directive = await role.run(rendered, state, ws.history)
        ws.directive = directive
        ws.steps.append(
            StepTrace(name=role.name, prompt=rendered, output=directive.model_dump(mode="json"))
        )

    return run


def director_step(role: Stage[PlanContext, TurnPlanBase], engine: Engine) -> StepFn:
    async def run(ws: TurnWorkspace) -> None:
        state = ws.state
        rendered = prompts.render_director(
            SceneSnapshot.of(state), engine.renderer(state), state.scenario, ws.prompt, ws.directive
        )
        plan = await role.run(rendered, PlanContext(engine=engine, state=state), ws.history)
        # Notes are read once: the draft carries none forward, so the next turn shows only new ones.
        ws.draft.pending_notes = ()
        ws.plan = plan
        ws.steps.append(
            StepTrace(name=role.name, prompt=rendered, output=plan.model_dump(mode="json"))
        )

    return run


def resolve_step(engine: Engine) -> StepFn:
    """Pure code: the action's procedure on the draft, then the plan's unconditional effects."""

    async def run(ws: TurnWorkspace) -> None:
        plan = ws.settled()
        ws.facts.extend(engine.resolve_action(ws.draft, plan, ws.rng))
        for effect in plan.effects:
            ws.facts.extend(apply_effect(ws.draft, effect, engine.default_rules))
        ws.draft = ws.draft.committed().draft()
        ws.evidence = narrator_evidence(ws.facts)
        ws.steps.append(StepTrace(name="resolve", output=ws.evidence))

    return run


def hook_step(engine: Engine) -> StepFn:
    """Runs before the Narrator, so a hook's consequences are narrated the turn they happen."""

    async def run(ws: TurnWorkspace) -> None:
        fired = fire_hooks(ws.draft, ws.facts, engine.default_rules)
        if fired:
            ws.facts.extend(fired)
            ws.draft = ws.draft.committed().draft()
            ws.evidence = narrator_evidence(ws.facts)
        ws.steps.append(
            StepTrace(
                name="hooks", output="\n".join(fact.trace for fact in fired) or "- (no hooks fired)"
            )
        )

    return run


def narrator_step(role: Stage[None, str], engine: Engine) -> StepFn:
    async def run(ws: TurnWorkspace) -> None:
        directive = ws.briefed()
        draft = ws.draft
        rendered = prompts.render_narrator(
            VisibleScene.of(SceneSnapshot.of(draft)),
            engine.renderer(draft),
            draft.scenario,
            focus=directive.focus,
            speaker_id=directive.speaker_id,
            evidence=ws.evidence,
            prompt=ws.prompt,
        )
        ws.narration = await role.run(rendered, None, ws.history)
        ws.steps.append(StepTrace(name=role.name, prompt=rendered, output=ws.narration))

    return run


def worldkeeper_step(
    role: Stage[None, WorldkeeperReport], engine: Engine, options: TurnOptions
) -> StepFn:
    async def run(ws: TurnWorkspace) -> None:
        draft = ws.draft
        rendered = prompts.render_worldkeeper(
            SceneSnapshot.of(draft),
            engine.renderer(draft),
            draft.scenario,
            prompt=ws.prompt,
            evidence=ws.evidence,
            narration=ws.narration,
        )
        report = await role.run(rendered, None, ws.history)
        for creation in admitted(report.creations, draft, options.max_growth):
            entity = _created_entity(creation, draft)
            ws.facts.append(draft.add(entity, engine.default_rules(entity)))
        ws.steps.append(
            StepTrace(name=role.name, prompt=rendered, output=report.model_dump(mode="json"))
        )

    return run


def plan_from_text(plan_type: type[TurnPlanBase]) -> Callable[[str], TurnPlanBase]:
    def parse(text: str) -> TurnPlanBase:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ModelRetry("Answer with one `turn_plan` tool call.")
        try:
            return plan_type.model_validate_json(text[start : end + 1])
        except ValidationError as invalid:
            first = invalid.errors()[0]
            where = ".".join(str(loc) for loc in first["loc"])
            raise ModelRetry(f"the plan did not validate — {where}: {first['msg']}") from invalid

    return parse


def scene_stage(settings: Settings) -> Stage[GameState, SceneDirective]:
    built = stage(
        "scene",
        settings,
        instructions=prompts.SCENE_DIRECTOR,
        output_type=NativeOutput(SceneDirective),
        deps_type=GameState,
    )

    def known(ctx: RunContext[GameState], directive: SceneDirective) -> SceneDirective:
        state = ctx.deps
        missing = sorted(set(directive.threads) - set(state.threads))
        if missing:
            raise ModelRetry(f"no such thread: {', '.join(missing)}")
        # A `reveal` naming anything but an unmet entity renders nothing
        unmet = {entity.id for entity in state.world.entities() if not entity.known}
        wrong = sorted(set(directive.reveal) - unmet)
        if wrong:
            raise ModelRetry(f"not something the player has yet to find: {', '.join(wrong)}")
        if fault := check_speaker(state, directive.speaker_id):
            raise ModelRetry(fault)
        return directive

    _ = built.agent.output_validator(known)
    return built


def director_stage(engine: Engine, settings: Settings) -> Stage[PlanContext, TurnPlanBase]:
    built = stage(
        "director",
        settings,
        instructions=f"{prompts.RULES_DIRECTOR}\n\n{engine.director_instructions}",
        output_type=[
            ToolOutput(engine.plan_type, name="turn_plan"),
            TextOutput(plan_from_text(engine.plan_type)),
        ],
        deps_type=PlanContext,
        toolsets=(engine.director_toolset,),
    )

    def legal(ctx: RunContext[PlanContext], plan: TurnPlanBase) -> TurnPlanBase:
        deps = ctx.deps
        refused = deps.engine.check_plan(deps.state, plan)
        if refused is not None:
            raise ModelRetry(refused)
        return plan

    _ = built.agent.output_validator(legal)
    return built


def narrator_stage(settings: Settings) -> Stage[None, str]:
    return stage(
        "narrator", settings, instructions=prompts.NARRATOR, output_type=str, deps_type=NoneType
    )


def worldkeeper_stage(settings: Settings) -> Stage[None, WorldkeeperReport]:
    return stage(
        "worldkeeper",
        settings,
        instructions=prompts.WORLDKEEPER,
        output_type=NativeOutput(WorldkeeperReport),
        deps_type=NoneType,
    )


def default_workflow(engine: Engine, settings: Settings, options: TurnOptions) -> TurnScript:
    """A new role is an inserted `(name, StepFn)` pair; nothing else changes."""
    director = director_stage(engine, settings)
    narrator = narrator_stage(settings)
    worldkeeper = worldkeeper_stage(settings)
    scene = scene_stage(settings)
    return (
        (scene.name, scene_step(scene, engine)),
        (director.name, director_step(director, engine)),
        ("resolve", resolve_step(engine)),
        ("hooks", hook_step(engine)),
        (narrator.name, narrator_step(narrator, engine)),
        (worldkeeper.name, worldkeeper_step(worldkeeper, engine, options)),
    )


async def run_turn(
    state: GameState,
    prompt: str,
    *,
    engine: Engine,
    script: TurnScript,
    options: TurnOptions,
    rng: Random,
    on_step: Callable[[str], None] | None = None,
) -> TurnResult:
    ws = TurnWorkspace(
        prompt=prompt,
        history=exchanges_to_messages(state.history[-options.history_window :]),
        state=state,
        draft=state.draft(),
        rng=rng,
    )
    for name, step in script:
        if on_step is not None:
            on_step(name)
        await step(ws)
    if ws.plan is None:
        raise ValueError("script finished without a turn plan")
    if not ws.narration:
        raise ValueError("script finished without a narration")
    draft = ws.draft
    draft.history = (*draft.history, Exchange(prompt=prompt, narration=ws.narration))
    draft.turn += 1
    final = draft.committed()
    engine.validate_state(final)
    return TurnResult(
        state=final,
        turn=Turn(
            prompt=prompt,
            facts=tuple(ws.facts),
            narration=ws.narration,
            steps=tuple(ws.steps),
        ),
    )


def admitted(creations: Sequence[Creation], state: GameState, maximum: int) -> tuple[Creation, ...]:
    """Locations sort first so an entity placed at one created this same report resolves."""
    seen = {entity.name.casefold() for entity in state.world.entities()}
    kept: list[Creation] = []
    for creation in creations:
        normalized = creation.name.casefold()
        if normalized in seen or len(kept) >= maximum:
            continue
        kept.append(creation)
        seen.add(normalized)
    return tuple(sorted(kept, key=lambda creation: creation.kind != "location"))


def _created_entity(creation: Creation, state: GameState) -> Entity:
    return Entity(
        id=slug(creation.name, state.world.all_ids()),
        kind=creation.kind,
        name=creation.name,
        brief=creation.brief,
        detail=creation.detail,
        known=True,
        parent_id=None if creation.kind == "location" else _placed(creation, state),
    )


def _placed(creation: Creation, state: GameState) -> EntityId:
    if creation.location is not None:
        wanted = creation.location.casefold()
        for entity in state.world.entities("location"):
            if entity.name.casefold() == wanted:
                return entity.id
    return state.player_location
