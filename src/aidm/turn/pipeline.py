from collections.abc import Callable, Sequence
from dataclasses import dataclass
from random import Random
from types import NoneType

from pydantic import BaseModel, Field, ValidationError
from pydantic_ai import ModelRetry, NativeOutput, RunContext, TextOutput, ToolOutput

from aidm.config import Settings
from aidm.engines.loader import Engine
from aidm.state.apply import fire_hooks
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


@dataclass(frozen=True, slots=True)
class Stages:
    """The turn's model-facing roles, built once per session."""

    scene: Stage[GameState, SceneDirective]
    director: Stage[PlanContext, TurnPlanBase]
    narrator: Stage[None, str]
    worldkeeper: Stage[None, WorldkeeperReport]


TURN_STEPS: tuple[str, ...] = ("scene", "director", "resolve", "hooks", "narrator", "worldkeeper")


def resolve_plan(
    engine: Engine, draft: GameState, plan: TurnPlanBase, rng: Random
) -> tuple[GameState, list[Fact]]:
    """Returns the revalidated draft the rest of the turn builds on."""
    facts = engine.resolve_action(draft, plan, rng)
    return draft.committed().draft(), facts


def apply_hooks(draft: GameState, facts: Sequence[Fact]) -> tuple[GameState, list[Fact]]:
    """Runs before the Narrator, so a hook's consequences are narrated the turn they happen."""
    fired = fire_hooks(draft, facts)
    return (draft.committed().draft() if fired else draft), fired


def apply_creations(draft: GameState, report: WorldkeeperReport, maximum: int) -> list[Fact]:
    return [
        draft.add(_created_entity(creation, draft))
        for creation in admitted(report.creations, draft, maximum)
    ]


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
        unmet = {entity.id for entity in state.world.entities.values() if not entity.known}
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


def build_stages(engine: Engine, settings: Settings) -> Stages:
    return Stages(
        scene=scene_stage(settings),
        director=director_stage(engine, settings),
        narrator=narrator_stage(settings),
        worldkeeper=worldkeeper_stage(settings),
    )


async def run_turn(
    state: GameState,
    prompt: str,
    *,
    engine: Engine,
    stages: Stages,
    options: TurnOptions,
    rng: Random,
    on_step: Callable[[str], None] | None = None,
) -> TurnResult:
    """One turn, in the order it happens. A new role is one more call in this sequence."""

    def announce(step: str) -> None:
        if on_step is not None:
            on_step(step)

    history = exchanges_to_messages(state.history[-options.history_window :])
    steps: list[StepTrace] = []
    draft = state.draft()
    snapshot = SceneSnapshot.of(state)

    announce("scene")
    # The Scene Director reads the full view and hands the Rules Director a directive.
    scene_prompt = prompts.render_director(snapshot, engine.renderer(state), state.scenario, prompt)
    directive = await stages.scene.run(scene_prompt, state, history)
    steps.append(_traced("scene", scene_prompt, directive))

    announce("director")
    plan_prompt = prompts.render_director(
        snapshot, engine.renderer(state), state.scenario, prompt, directive
    )
    plan = await stages.director.run(plan_prompt, PlanContext(engine=engine, state=state), history)
    # Notes are read once: the draft carries none forward, so the next turn shows only new ones.
    draft.pending_notes = ()
    steps.append(_traced("director", plan_prompt, plan))

    announce("resolve")
    draft, facts = resolve_plan(engine, draft, plan, rng)
    evidence = narrator_evidence(facts)
    steps.append(StepTrace(name="resolve", output=evidence))

    announce("hooks")
    draft, fired = apply_hooks(draft, facts)
    if fired:
        facts.extend(fired)
        evidence = narrator_evidence(facts)
    fired_trace = "\n".join(fact.trace for fact in fired) or "- (no hooks fired)"
    steps.append(StepTrace(name="hooks", output=fired_trace))

    announce("narrator")
    narrator_prompt = prompts.render_narrator(
        VisibleScene.of(SceneSnapshot.of(draft)),
        engine.renderer(draft),
        draft.scenario,
        focus=directive.focus,
        speaker_id=directive.speaker_id,
        evidence=evidence,
        prompt=prompt,
    )
    narration = await stages.narrator.run(narrator_prompt, None, history)
    if not narration:
        raise ValueError("the narrator answered with nothing")
    steps.append(StepTrace(name="narrator", prompt=narrator_prompt, output=narration))

    announce("worldkeeper")
    keeper_prompt = prompts.render_worldkeeper(
        SceneSnapshot.of(draft),
        engine.renderer(draft),
        draft.scenario,
        prompt=prompt,
        evidence=evidence,
        narration=narration,
    )
    report = await stages.worldkeeper.run(keeper_prompt, None, history)
    facts.extend(apply_creations(draft, report, options.max_growth))
    steps.append(_traced("worldkeeper", keeper_prompt, report))

    draft.history = (*draft.history, Exchange(prompt=prompt, narration=narration))
    draft.turn += 1
    engine.commit(draft)
    final = draft.committed()
    return TurnResult(
        state=final,
        turn=Turn(prompt=prompt, facts=tuple(facts), narration=narration, steps=tuple(steps)),
    )


def _traced(name: str, rendered: str, output: BaseModel) -> StepTrace:
    return StepTrace(name=name, prompt=rendered, output=output.model_dump(mode="json"))


def admitted(creations: Sequence[Creation], state: GameState, maximum: int) -> tuple[Creation, ...]:
    """Locations sort first so an entity placed at one created this same report resolves."""
    seen = {entity.name.casefold() for entity in state.world.entities.values()}
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
        for entity in state.world.of_kind("location"):
            if entity.name.casefold() == wanted:
                return entity.id
    return state.player_location
