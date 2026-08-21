from collections.abc import Sequence

from pydantic_ai import Agent, ModelRetry, RunContext, ToolOutput
from pydantic_ai.toolsets import FunctionToolset

from aidm.config import Settings
from aidm.content.io import load_scenario
from aidm.content.model import Scenario
from aidm.llm import build_agent
from aidm.state.model import Slug

from .draft import ScenarioPatch, WorldDraft
from .playability import FULL, Brief, Playtest, playability

# An author works in passes; past REQUEST_LIMIT calls the run is spinning, not authoring.
REQUEST_LIMIT = 40
WORKED_EXAMPLE = "whispering-vault"


def authoring_toolset(
    playing: Sequence[Playtest],
    config: Settings,
    brief: Brief = FULL,
) -> FunctionToolset[WorldDraft]:
    def worked_example() -> str:
        """The shipped scenario in the draft shape patches are written in: the bar to match."""
        return WorldDraft.of(load_scenario(config.scenarios_dir, WORKED_EXAMPLE)).as_json()

    def scenario_so_far(ctx: RunContext[WorldDraft]) -> str:
        """The whole draft as it stands, as pretty JSON: read it back before modifying or
        removing anything, so every id you name is one it actually holds."""
        return ctx.deps.as_json()

    def write(ctx: RunContext[WorldDraft], patch: ScenarioPatch) -> str:
        """Apply one patch to the draft. An element whose id the draft already holds is replaced
        whole, so send the complete element when modifying one; `remove` drops ids from whichever
        collection holds them. Returns each change as `created|modified|deleted kind name[id]`."""
        try:
            return ctx.deps.apply(patch)
        except ValueError as refused:
            raise ModelRetry(str(refused)) from refused

    def validate_scenario(ctx: RunContext[WorldDraft]) -> str:
        """Whether the draft plays: 'ok', or the exact reason it will not. Fix what it names and
        call it again; the scenario is only done once it answers 'ok'."""
        return playability(ctx.deps, playing, brief) or "ok"

    return FunctionToolset(tools=[worked_example, scenario_so_far, write, validate_scenario])


def world_agent(
    playing: Sequence[Playtest],
    config: Settings,
    brief: Brief = FULL,
) -> Agent[WorldDraft, str]:
    """Ends on the `finish` tool, not bare text: a tool-only author would never end its own turn."""

    def playable(ctx: RunContext[WorldDraft], summary: str) -> str:
        if reason := playability(ctx.deps, playing, brief):
            raise ModelRetry(f"the draft does not play yet, so it is not finished: {reason}")
        return summary

    return build_agent(
        "scenario_creator",
        config,
        instructions=brief.instructions,
        output_type=ToolOutput(
            str,
            name="finish",
            description=(
                "End authorship. Call this only once `validate_scenario` answers ok; its argument "
                "is two or three sentences on what you authored."
            ),
        ),
        deps_type=WorldDraft,
        toolsets=[authoring_toolset(playing, config, brief)],
        validator=playable,
    )


def world_prompt(slug: Slug, premise: str, sourced: bool) -> str:
    heading = "SOURCE DOCUMENT:" if sourced else "PREMISE:"
    return f"{heading}\n{premise}\n\nWill be saved as: {slug!r}"


def summarize(scenario: Scenario) -> str:
    return (
        f"{scenario.meta.title}\n"
        f"{len(scenario.world.entities)} entities, {len(scenario.world.threads)} threads"
    )
