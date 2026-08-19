from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from types import NoneType

from pydantic import Field
from pydantic_ai import (
    Agent,
    ModelRetry,
    NativeOutput,
    RunContext,
    ToolOutput,
)
from pydantic_ai.messages import ModelMessage
from pydantic_ai.toolsets import FunctionToolset

from aidm.config import Settings
from aidm.content.authored import ScenarioOverlay, ScenarioWorld
from aidm.content.store import ENCODING, WORLD_FILE, engine_text
from aidm.engines.engine import Engine
from aidm.engines.sheets import SheetBase
from aidm.llm import build_agent
from aidm.state.base import EngineId, EntityId, Frozen, Slug

from .draft import ScenarioPatch, WorldDraft
from .playability import FULL, Brief, Playtest, playability

ROUNDS = 3
# An author works in passes; past REQUEST_LIMIT calls the run is spinning, not authoring.
REQUEST_LIMIT = 40
WORKED_EXAMPLE = "whispering-vault"

_PROMPTS_DIR = Path(__file__).parents[1] / "prompts"

OVERLAY_INSTRUCTIONS = engine_text(_PROMPTS_DIR / "scenario_overlay.md")


class TypedOverlay[S: SheetBase](Frozen):
    entities: dict[EntityId, S] = Field(default_factory=dict)


async def ask_until_playable[T](
    agent: Agent[NoneType, T], prompt: str, check: Callable[[T], None]
) -> T:
    """`check` raises ValueError; the reason goes back to the author, up to ROUNDS times."""
    history: list[ModelMessage] = []
    ask = prompt
    reason = ""
    for _ in range(ROUNDS):
        result = await agent.run(ask, deps=None, message_history=history)
        try:
            check(result.output)
        except ValueError as refused:
            reason = str(refused)
            history = list(result.all_messages())
            ask = f"That will not play:\n\n{reason}\n\nWrite the whole answer again, fixed."
            continue
        return result.output
    raise ValueError(f"no playable answer in {ROUNDS} rounds. Last refusal: {reason}")


def authoring_toolset(
    slug: Slug,
    playing: Sequence[Playtest],
    config: Settings,
    brief: Brief = FULL,
) -> FunctionToolset[WorldDraft]:
    def worked_example() -> str:
        """The shipped scenario's world.json: the format and the quality bar to match."""
        return (config.scenarios_dir / WORKED_EXAMPLE / WORLD_FILE).read_text(encoding=ENCODING)

    def scenario_so_far(ctx: RunContext[WorldDraft]) -> str:
        """The whole draft as it stands, as pretty JSON: read it back before modifying or
        removing anything, so every id you name is one it actually holds."""
        return ctx.deps.as_json()

    def write(ctx: RunContext[WorldDraft], patch: ScenarioPatch) -> str:
        """Apply one patch to the draft. An element whose id the draft already holds is replaced
        whole, so send the complete element when modifying one; `remove` drops ids from whichever
        collection holds them. Returns a short summary of what changed."""
        try:
            return ctx.deps.apply(patch)
        except ValueError as refused:
            raise ModelRetry(str(refused)) from refused

    def validate_scenario(ctx: RunContext[WorldDraft]) -> str:
        """Whether the draft plays: 'ok', or the exact reason it will not. Fix what it names and
        call it again; the scenario is only done once it answers 'ok'."""
        return playability(ctx.deps, slug, playing, brief) or "ok"

    return FunctionToolset(tools=[worked_example, scenario_so_far, write, validate_scenario])


def world_agent(
    slug: Slug,
    playing: Sequence[Playtest],
    config: Settings,
    brief: Brief = FULL,
) -> Agent[WorldDraft, str]:
    """Ends on the `finish` tool, not bare text: a tool-only author would never end its own turn."""

    def playable(ctx: RunContext[WorldDraft], summary: str) -> str:
        if reason := playability(ctx.deps, slug, playing, brief):
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
        toolsets=[authoring_toolset(slug, playing, config, brief)],
        validator=playable,
    )


def overlay_agent(
    engine: Engine[SheetBase], config: Settings
) -> Agent[NoneType, TypedOverlay[SheetBase]]:
    model = TypedOverlay[engine.sheet_type]  # pyright: ignore[reportUnknownVariableType]
    return build_agent(
        "scenario_creator",
        config,
        instructions=OVERLAY_INSTRUCTIONS,
        output_type=NativeOutput(model),
        deps_type=NoneType,
    )


def world_prompt(slug: Slug, premise: str, sourced: bool) -> str:
    heading = "SOURCE DOCUMENT:" if sourced else "PREMISE:"
    return f"{heading}\n{premise}\n\nWill be saved as: {slug!r}"


def _overlay_prompt(engine: Engine[SheetBase], world: ScenarioWorld, config: Settings) -> str:
    example = engine_text(config.scenarios_dir / WORKED_EXAMPLE / f"{engine.id}.json")
    return (
        f"ENGINE:\n{engine.id}\n\n"
        f"WORLD:\n{world.model_dump_json(indent=2)}\n\n"
        f"WORKED EXAMPLE:\n{example}"
    )


def _as_overlay(typed: TypedOverlay[SheetBase]) -> ScenarioOverlay:
    return ScenarioOverlay(
        entities={
            entity_id: sheet.model_dump(mode="json", exclude_defaults=True)
            for entity_id, sheet in typed.entities.items()
        }
    )


async def authored_overlay(
    playtest: Playtest, slug: Slug, world: ScenarioWorld, config: Settings
) -> ScenarioOverlay:
    engine = playtest.engine

    def check(typed: TypedOverlay[SheetBase]) -> None:
        playtest.check(slug, world, _as_overlay(typed))

    typed = await ask_until_playable(
        overlay_agent(engine, config), _overlay_prompt(engine, world, config), check
    )
    return _as_overlay(typed)


def summarize(world: ScenarioWorld, overlays: Mapping[EngineId, ScenarioOverlay]) -> str:
    lines = [
        world.meta.title,
        f"{len(world.entities)} entities, {len(world.threads)} threads, {len(world.hooks)} hooks",
    ]
    for engine_id, overlay in overlays.items():
        lines.append(f"{engine_id}: {len(overlay.entities)} entities with mechanics")
    return "\n".join(lines)
