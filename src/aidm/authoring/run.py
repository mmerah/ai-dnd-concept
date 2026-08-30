import json
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

from pydantic import JsonValue
from pydantic_ai import Agent, ModelRetry, RunContext, Tool, ToolOutput, UsageLimits
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.test import TestModel
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai.usage import RunUsage

from aidm.authoring.draft import (
    Draft,
    PlaytestCheck,
    ScenarioPatch,
    check_new_scenario,
    extension_prompt,
    patch_refusal,
    playtest_check,
    scenario_refusal,
    world_prompt,
    write_draft,
)
from aidm.config import Settings
from aidm.content.io import engine_text, read_scenarios
from aidm.content.model import AuthoringBrief, AuthoringTool, Character
from aidm.engines.core import Engine, mechanics_delta
from aidm.llm import build_agent, schema_of
from aidm.state.entities import EngineId, Slug
from aidm.state.model import Game
from aidm.state.tools import Play
from aidm.world.authoring import diff

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _example(settings: Settings, engine_id: EngineId) -> str | None:
    """The example must speak the authored engine's `rules` dialect, or it teaches refusals."""
    first = next(read_scenarios(settings.scenarios_dir, (engine_id,)), None)
    return None if first is None else Draft.from_scenario(first[1]).as_json()


def _instructions(settings: Settings, brief: AuthoringBrief, playing: PlaytestCheck) -> str:
    mechanics = json.dumps(playing.character.mechanics, indent=2)
    example = _example(settings, playing.engine.id)
    shown = (
        ()
        if example is None
        else (engine_text(_PROMPTS_DIR / "scenario_example.md"), f"```json\n{example}\n```")
    )
    return "\n\n".join(
        (
            brief.bar_prompt,
            *shown,
            engine_text(_PROMPTS_DIR / "scenario_rules.md"),
            f"```json\n{mechanics}\n```",
            brief.guidance,
        )
    )


def draft_context(draft: Draft, tool_name: str | None = None) -> RunContext[Draft]:
    # A RunContext needs a model; no authoring tool reads one.
    return RunContext(deps=draft, model=TestModel(), usage=RunUsage(), tool_name=tool_name)


def authoring_toolset(playing: PlaytestCheck, brief: AuthoringBrief) -> FunctionToolset[Draft]:
    def answer(draft: Draft, changed: str) -> str:
        standing = scenario_refusal(draft, playing, brief) or (
            "it plays. Read it back and judge it as a thing to play before you finish."
        )
        return f"{changed}\n\nDRAFT: {standing}"

    def scenario_so_far(ctx: RunContext[Draft]) -> str:
        """Read the complete current draft as formatted JSON."""
        return ctx.deps.as_json()

    def write(ctx: RunContext[Draft], patch: ScenarioPatch) -> str:
        """Apply one update and return the changes plus what the draft still needs."""
        if refused := patch_refusal(patch, brief.settled):
            raise ModelRetry(refused)
        try:
            return answer(ctx.deps, ctx.deps.apply(patch, playing.engine))
        except ValueError as refused:
            raise ModelRetry(str(refused)) from refused

    def as_tool(one: AuthoringTool) -> Tool[Draft]:
        async def call(ctx: RunContext[Draft], **raw: JsonValue) -> str:
            try:
                return answer(ctx.deps, one.apply(ctx.deps.world, raw))
            except ValueError as refused:
                raise ModelRetry(str(refused)) from refused

        return Tool.from_schema(
            call,
            one.name,
            one.description,
            schema_of(one.args),
            takes_ctx=True,
            sequential=True,
        )

    return FunctionToolset(tools=[scenario_so_far, write, *(as_tool(one) for one in brief.tools)])


def scenario_agent(
    playing: PlaytestCheck, settings: Settings, brief: AuthoringBrief
) -> Agent[Draft, str]:
    def playable(ctx: RunContext[Draft], summary: str) -> str:
        if reason := scenario_refusal(ctx.deps, playing, brief):
            raise ModelRetry(f"the draft does not play yet, so it is not finished: {reason}")
        return summary

    return build_agent(
        "scenario_creator",
        settings,
        instructions=_instructions(settings, brief, playing),
        output_type=ToolOutput(
            str,
            name="finish",
            description="Finish a playable draft with a 2-3 sentence summary.",
        ),
        deps_type=Draft,
        toolsets=[authoring_toolset(playing, brief)],
        validator=playable,
    )


@dataclass(kw_only=True)
class AuthoringRun:
    settings: Settings
    draft: Draft
    playing: PlaytestCheck
    brief: AuthoringBrief
    toolset: FunctionToolset[Draft]
    opening_prompt: str
    history: list[ModelMessage] = field(default_factory=list)

    @cached_property
    def agent(self) -> Agent[Draft, str]:
        """Built on first send: code mode drives the toolset itself and may hold no api key."""
        return scenario_agent(self.playing, self.settings, self.brief)

    async def send(self, instruction: str) -> str:
        result = await self.agent.run(
            instruction,
            deps=self.draft,
            message_history=self.history,
            usage_limits=UsageLimits(request_limit=self.settings.authoring.request_limit),
        )
        self.history = list(result.all_messages())
        return result.output

    def refusal(self) -> str | None:
        return scenario_refusal(self.draft, self.playing, self.brief)


@dataclass(kw_only=True)
class GrowthRun(AuthoringRun):
    base: Game

    def play(self) -> Play:
        base, draft = self.base.world, self.draft.world
        delta = mechanics_delta(base.mechanics, draft.mechanics)
        return diff(base, draft, delta, self.playing.engine.mechanics_patch)


@dataclass(kw_only=True)
class ScenarioRun(AuthoringRun):
    slug: Slug
    premise: str
    document: Path | None
    grows: bool = False
    busy: bool = False

    def write(self) -> str:
        """Revalidates the draft — the agent's 'ok' is never trusted — before it reaches disk."""
        if reason := self.refusal():
            raise ValueError(f"the draft does not play: {reason}")
        return write_draft(
            self.settings,
            self.slug,
            self.draft,
            self.playing.engine.id,
            self.playing.packs,
            self.grows,
            self.document or self.premise,
        )


_HOW_TO_WORK = (
    "Write with `write`, use your other tools for what `write` does not set, and read the whole "
    "draft back with `scenario_so_far` whenever you have lost track of it. Each answer ends with "
    "what the draft still needs. Call `{finish}` once it plays."
)


def briefing(run: AuthoringRun, finish: str) -> str:
    return "\n\n".join(
        (
            _instructions(run.settings, run.brief, run.playing),
            run.opening_prompt,
            _HOW_TO_WORK.format(finish=finish),
        )
    )


def growth_run(settings: Settings, engine: Engine, character: Character, state: Game) -> GrowthRun:
    brief = engine.authoring_brief(state.packs, state.world, False)
    playing = PlaytestCheck(engine=engine, character=character, packs=state.packs)
    return GrowthRun(
        settings=settings,
        draft=Draft.from_game(state),
        playing=playing,
        brief=brief,
        toolset=authoring_toolset(playing, brief),
        opening_prompt=extension_prompt(settings, state),
        base=state,
    )


def scenario_run(
    settings: Settings,
    engine: Engine,
    slug: Slug,
    premise: str,
    grows: bool,
    document: Path | None,
    *,
    packs: tuple[Slug, ...] = (),
    art_style: str = "",
) -> ScenarioRun:
    check_new_scenario(settings, slug, premise, document)
    playing = playtest_check(settings, engine, packs)
    brief = engine.authoring_brief(playing.packs, None, grows)
    return ScenarioRun(
        settings=settings,
        draft=Draft(art_style=art_style),
        playing=playing,
        brief=brief,
        toolset=authoring_toolset(playing, brief),
        opening_prompt=world_prompt(settings, slug, premise, document),
        slug=slug,
        premise=premise,
        document=document,
        grows=grows,
    )
