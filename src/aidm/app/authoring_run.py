from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

from pydantic_ai import Agent, ModelRetry, RunContext, ToolOutput, UsageLimits
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.test import TestModel
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai.usage import RunUsage

from aidm.app.authoring import (
    OPENING_SLICE,
    WHOLE_SCENARIO,
    AuthoringBrief,
    ExtensionPatch,
    PlaytestCheck,
    ScenarioDraft,
    ScenarioPatch,
    check_new_scenario,
    extend_brief,
    extension_patch,
    extension_prompt,
    patch_refusal,
    playtest_checks,
    scenario_refusal,
    world_prompt,
    write_draft,
)
from aidm.config import Settings
from aidm.content.io import engine_text, load_scenario
from aidm.content.model import Character
from aidm.engines.core import Engine
from aidm.llm import build_agent
from aidm.state.entities import EngineId, EntityId, Slug
from aidm.state.model import Game

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _instructions(settings: Settings, brief: AuthoringBrief) -> str:
    """The worked example rides in the prompt, so reading it costs no tool call."""
    example = ScenarioDraft.from_scenario(
        load_scenario(settings.scenarios_dir, settings.authoring.worked_example)
    ).as_json()
    return "\n\n".join(
        (
            engine_text(_PROMPTS_DIR / "scenario_world.md"),
            engine_text(_PROMPTS_DIR / brief.bar_prompt),
            engine_text(_PROMPTS_DIR / "scenario_example.md"),
            f"```json\n{example}\n```",
        )
    )


def authoring_context(
    draft: ScenarioDraft, tool_name: str | None = None
) -> RunContext[ScenarioDraft]:
    # A RunContext needs a model; no authoring tool reads one.
    return RunContext(deps=draft, model=TestModel(), usage=RunUsage(), tool_name=tool_name)


def authoring_toolset(
    playing: Sequence[PlaytestCheck],
    brief: AuthoringBrief = WHOLE_SCENARIO,
) -> FunctionToolset[ScenarioDraft]:
    def answer(draft: ScenarioDraft, changed: str) -> str:
        standing = scenario_refusal(draft, playing, brief) or (
            "it plays. Read it back and judge it as a thing to play before you finish."
        )
        return f"{changed}\n\nDRAFT: {standing}"

    def scenario_so_far(ctx: RunContext[ScenarioDraft]) -> str:
        """Read the complete current draft as formatted JSON."""
        return ctx.deps.as_json()

    def write(ctx: RunContext[ScenarioDraft], patch: ScenarioPatch) -> str:
        """Apply one update and return the changes plus what the draft still needs."""
        if refused := patch_refusal(patch, brief.settled):
            raise ModelRetry(refused)
        try:
            return answer(ctx.deps, ctx.deps.apply(patch))
        except ValueError as refused:
            raise ModelRetry(str(refused)) from refused

    def connect(
        ctx: RunContext[ScenarioDraft],
        from_id: EntityId,
        to_id: EntityId,
        known: bool = False,
        locked: bool = False,
        one_way: bool = False,
    ) -> str:
        """Connect two locations already in the draft.

        Args:
            from_id: Exact id of the first location.
            to_id: Exact id of the second location.
            known: Whether the player knows this route at the start.
            locked: Whether the route starts locked.
            one_way: Whether the route goes only from the first location to the second.
        """
        if {from_id, to_id} <= brief.settled:
            raise ModelRetry(
                f"{from_id!r} and {to_id!r} are both the live game's, and nothing here can take "
                "a way between them back. Join one of them to a location this pass wrote."
            )
        try:
            return answer(ctx.deps, ctx.deps.connect(from_id, to_id, known, locked, one_way))
        except ValueError as refused:
            raise ModelRetry(str(refused)) from refused

    return FunctionToolset(tools=[scenario_so_far, write, connect])


def scenario_agent(
    playing: Sequence[PlaytestCheck],
    settings: Settings,
    brief: AuthoringBrief = WHOLE_SCENARIO,
) -> Agent[ScenarioDraft, str]:
    """Ends on the `finish` tool, not bare text: a tool-only author would never end its own turn."""

    def playable(ctx: RunContext[ScenarioDraft], summary: str) -> str:
        if reason := scenario_refusal(ctx.deps, playing, brief):
            raise ModelRetry(f"the draft does not play yet, so it is not finished: {reason}")
        return summary

    return build_agent(
        "scenario_creator",
        settings,
        instructions=_instructions(settings, brief),
        output_type=ToolOutput(
            str,
            name="finish",
            description="Finish a playable draft with a 2-3 sentence summary.",
        ),
        deps_type=ScenarioDraft,
        toolsets=[authoring_toolset(playing, brief)],
        validator=playable,
    )


@dataclass(kw_only=True)
class AuthoringRun:
    """One draft under authorship, many turns; the UI drives `send`, code mode the toolset."""

    settings: Settings
    draft: ScenarioDraft
    playing: tuple[PlaytestCheck, ...]
    brief: AuthoringBrief
    toolset: FunctionToolset[ScenarioDraft]
    opening_prompt: str
    history: list[ModelMessage] = field(default_factory=list)

    @cached_property
    def agent(self) -> Agent[ScenarioDraft, str]:
        """Built on first send: code mode drives the toolset itself and may hold no api key."""
        return scenario_agent(self.playing, self.settings, self.brief)

    async def send(self, instruction: str) -> str:
        """One agent turn against the same draft and the same history."""
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
    """Grows a world in play; `base` is the state the finished draft is diffed against."""

    base: Game

    def patch(self) -> ExtensionPatch:
        return extension_patch(self.base.world, self.draft)


@dataclass(kw_only=True)
class ScenarioRun(AuthoringRun):
    """Writes a whole new scenario; needs no open game."""

    slug: Slug
    premise: str
    document: Path | None
    engines: tuple[EngineId, ...]
    art_style: str = ""
    busy: bool = False

    def write(self) -> str:
        """Revalidates the draft — the agent's 'ok' is never trusted — before it reaches disk."""
        if reason := self.refusal():
            raise ValueError(f"the draft does not play: {reason}")
        # The form's style overrides whatever the author wrote from the source's own tone.
        self.draft.art_style = self.art_style or self.draft.art_style
        return write_draft(
            self.settings, self.slug, self.draft, self.engines, self.document or self.premise
        )


_HOW_TO_WORK = (
    "Write with `write`, join locations with `connect`, and read the whole draft back with "
    "`scenario_so_far` whenever you have lost track of it. Each answer ends with what the draft "
    "still needs. Call `{finish}` with a two or three sentence summary once it plays."
)


def briefing(settings: Settings, brief: AuthoringBrief, prompt: str, finish: str) -> str:
    return "\n\n".join((_instructions(settings, brief), prompt, _HOW_TO_WORK.format(finish=finish)))


def growth_run(settings: Settings, engine: Engine, character: Character, state: Game) -> GrowthRun:
    brief = extend_brief(state.world)
    playing = (PlaytestCheck(engine=engine, character=character),)
    return GrowthRun(
        settings=settings,
        draft=ScenarioDraft.from_game(state),
        playing=playing,
        brief=brief,
        toolset=authoring_toolset(playing, brief),
        opening_prompt=extension_prompt(settings, state),
        base=state,
    )


def scenario_run(
    settings: Settings,
    slug: Slug,
    premise: str,
    grows: bool,
    engines: Sequence[EngineId],
    document: Path | None,
    *,
    brief: AuthoringBrief | None = None,
    art_style: str = "",
) -> ScenarioRun:
    check_new_scenario(settings, slug, premise, document)
    if brief is None:
        brief = OPENING_SLICE if grows else WHOLE_SCENARIO
    playing = playtest_checks(settings, engines)
    return ScenarioRun(
        settings=settings,
        draft=ScenarioDraft(grows=grows),
        playing=playing,
        brief=brief,
        toolset=authoring_toolset(playing, brief),
        opening_prompt=world_prompt(settings, slug, premise, document),
        slug=slug,
        premise=premise,
        document=document,
        engines=tuple(engines),
        art_style=art_style,
    )
