from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cached_property
from random import Random

from pydantic_ai import (
    Agent,
    ModelRetry,
    NativeOutput,
    RunContext,
    Tool,
    UnexpectedModelBehavior,
)
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.output import OutputSpec
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.toolsets import AbstractToolset, FunctionToolset

from aidm.config import ProviderConfig, Role, RoleConfig, Settings
from aidm.content.sources import CanonSource
from aidm.engines.advancement import Advancement, Offer, ProposalBase
from aidm.engines.loader import Engine
from aidm.engines.sheets import SheetBase
from aidm.engines.transact import transact
from aidm.state.base import EntityId, Kind
from aidm.state.plan import DirectorBeat, check_draft
from aidm.state.turn import WorldkeeperReport
from aidm.state.world import Exchange, GameState, Narration

from . import prompts
from .expansion import MAX_EXPANSIONS, ExpansionPatch, Expansions, apply_patch, written
from .scene import SceneSnapshot, VisibleScene


@dataclass(frozen=True)
class Stage[Deps, Out]:
    name: str
    instructions: str
    output_type: OutputSpec[Out]
    deps_type: type[Deps]
    role: RoleConfig
    provider: ProviderConfig
    toolsets: Sequence[AbstractToolset[Deps]] = ()

    @cached_property
    def agent(self) -> Agent[Deps, Out]:
        provider = OpenAIProvider(
            base_url=self.provider.base_url,
            api_key=self.provider.api_key.get_secret_value(),
        )
        model = OpenAIChatModel(self.role.model, provider=provider)
        settings = OpenAIChatModelSettings(
            max_tokens=self.role.max_tokens,
            openai_reasoning_effort=self.role.reasoning_effort,
        )
        if self.role.temperature is not None:
            settings["temperature"] = self.role.temperature
        return Agent(
            model,
            name=self.name,
            output_type=self.output_type,
            instructions=self.instructions,
            deps_type=self.deps_type,
            toolsets=list(self.toolsets),
            retries=self.role.retries,
            model_settings=settings,
        )

    async def run(self, prompt: str, deps: Deps, recent: Sequence[ModelMessage] = ()) -> Out:
        result = await self.agent.run(prompt, deps=deps, message_history=list(recent))
        return result.output

    @classmethod
    def of[D, O](
        cls,
        name: Role,
        settings: Settings,
        *,
        instructions: str,
        output_type: OutputSpec[O],
        deps_type: type[D],
        toolsets: Sequence[AbstractToolset[D]] = (),
        validator: Callable[[RunContext[D], O], O] | None = None,
    ) -> "Stage[D, O]":
        role = settings.role(name)
        built = Stage(
            name=name,
            instructions=instructions,
            output_type=output_type,
            deps_type=deps_type,
            role=role,
            provider=settings.providers.for_name(role.provider),
            toolsets=toolsets,
        )
        if validator is not None:
            _ = built.agent.output_validator(validator)
        return built


@dataclass(frozen=True, slots=True)
class PlanContext:
    """What a planning call is resolved against: the engine, the state its answer is judged on —
    the committed state for the turn's plan, the turn's own draft once it is under way — and the
    dice and expansion record the `expand_world` tool writes through."""

    engine: Engine[SheetBase]
    state: GameState
    rng: Random
    expansions: Expansions
    settle: bool = False


@dataclass(frozen=True, slots=True)
class AdvancementContext:
    advancement: Advancement
    state: GameState
    offer: Offer


@dataclass(frozen=True, slots=True)
class Stages:
    """The turn's model-facing roles, built once per session."""

    director: Stage[PlanContext, DirectorBeat]
    narrator: Stage[VisibleScene, Narration]
    worldkeeper: Stage[GameState, WorldkeeperReport]
    # Built only when the adventure may expand; the turn reaches it through the Director's tool.
    expander: Stage[PlanContext, ExpansionPatch] | None = None


def director_stage(
    engine: Engine[SheetBase],
    settings: Settings,
    expand_tool: FunctionToolset[PlanContext] | None = None,
) -> Stage[PlanContext, DirectorBeat]:
    """One role for the turn's first ask and every later beat: `PlanContext.settle` is the only
    thing that changes what a call may legally answer."""

    def legal(ctx: RunContext[PlanContext], plan: DirectorBeat) -> DirectorBeat:
        if ctx.deps.settle and plan.roll is not None:
            raise ModelRetry(
                "this is the turn's last beat: leave `roll` null and write only what the dice "
                "already settled."
            )
        if refused := ctx.deps.engine.check_beat(ctx.deps.state, plan):
            raise ModelRetry(refused)
        return plan

    toolsets: list[AbstractToolset[PlanContext]] = list(engine.director_toolsets)
    if expand_tool is not None:
        toolsets.append(expand_tool)
    return Stage.of(
        "director",
        settings,
        instructions=f"{prompts.DIRECTOR}\n\n{engine.director_instructions}",
        output_type=NativeOutput(DirectorBeat),
        deps_type=PlanContext,
        toolsets=toolsets,
        validator=legal,
    )


def narrator_stage(settings: Settings) -> Stage[VisibleScene, Narration]:
    def attributed(ctx: RunContext[VisibleScene], narration: Narration) -> Narration:
        """The leak rule holds through the validator, not through trust."""
        present = {ctx.deps.player.id, *(entity.id for entity in ctx.deps.here)}
        strangers = sorted(
            {
                line.speaker_id
                for line in narration.lines
                if line.speaker_id is not None and line.speaker_id not in present
            }
        )
        if strangers:
            raise ModelRetry(
                f"nobody here has id {', '.join(strangers)}. Only the player or someone here with "
                "them speaks; leave `speaker_id` null for narration."
            )
        return narration

    return Stage.of(
        "narrator",
        settings,
        instructions=prompts.NARRATOR,
        output_type=NativeOutput(Narration),
        deps_type=VisibleScene,
        validator=attributed,
    )


def worldkeeper_stage(settings: Settings) -> Stage[GameState, WorldkeeperReport]:
    def known(ctx: RunContext[GameState], report: WorldkeeperReport) -> WorldkeeperReport:
        state = ctx.deps
        strangers = sorted(
            {
                memory.owner_id
                for memory in report.memories
                if memory.owner_id is not None and memory.owner_id not in state.world.entities
            }
        )
        if strangers:
            raise ModelRetry(
                f"nobody holds a memory who does not exist: {', '.join(strangers)}. Use an exact "
                "id from the catalogue, or null for the world."
            )
        return report

    return Stage.of(
        "worldkeeper",
        settings,
        instructions=prompts.WORLDKEEPER,
        output_type=NativeOutput(WorldkeeperReport),
        deps_type=GameState,
        validator=known,
    )


def expander_stage(settings: Settings) -> Stage[PlanContext, ExpansionPatch]:
    """A patch that would not commit is refused here, against a throwaway draft, so the turn's own
    draft only ever sees canon that lands."""

    def sound(ctx: RunContext[PlanContext], patch: ExpansionPatch) -> ExpansionPatch:
        deps = ctx.deps

        # The whole mutation sequence the real one will run, hooks and seeding included: whatever
        # a thinner trial skipped would fail the turn outright instead of asking again.
        def trial(draft: GameState) -> object:
            return transact(
                deps.engine, draft, lambda copy: apply_patch(deps.engine, copy, patch), Random(0)
            )

        if refused := check_draft(deps.state, trial):
            raise ModelRetry(refused)
        return patch

    return Stage.of(
        "expander",
        settings,
        instructions=prompts.EXPANDER,
        output_type=NativeOutput(ExpansionPatch),
        deps_type=PlanContext,
        validator=sound,
    )


def expansion_toolset(
    engine: Engine[SheetBase],
    expander: Stage[PlanContext, ExpansionPatch],
    source: CanonSource,
) -> FunctionToolset[PlanContext]:
    async def expand_world(
        ctx: RunContext[PlanContext],
        kind: Kind,
        anchor_id: EntityId,
        need: str,
        queries: tuple[str, ...] = (),
    ) -> str:
        """Write canon this world does not hold yet, when what the turn reaches for is genuinely
        absent — never as a replacement for something that already exists. Read EXISTS BUT THE
        PLAYER DOES NOT KNOW IT YET first: while anything there answers the turn, this call is
        wrong, and so is calling it for a turn that reaches for nothing in particular. Name the
        kind of thing missing, the exact id of the entity it hangs off, the need it fills in a
        sentence of plain words, and in `queries` the words the adventure's own text would use for
        it — names, places, and objects — which is how the source is looked up for you. What comes
        back is unknown to the player, so reveal it or move them to it in this same plan. Returns
        the ids written."""
        deps, draft = ctx.deps, ctx.deps.state
        anchor = draft.world.find(anchor_id)
        if anchor is None:
            raise ModelRetry(f"nothing here has id {anchor_id!r}. Use an id you were shown.")
        if deps.expansions.capped():
            raise ModelRetry(
                f"you have already reached for new canon {MAX_EXPANSIONS} times this turn. Plan "
                "the rest with what already exists."
            )
        # The anchor name is folded in because a `need` written as an identifier retrieves nothing
        # on its own.
        found = source.passages(" ".join((anchor.name, need, *queries)))
        if not found:
            raise ModelRetry(
                f"the source holds nothing about {need!r}. Ask again with the words the "
                "adventure's own text would use for it, or plan this turn with what exists."
            )
        asked = (
            f"kind: {kind}\nanchor: {anchor.name}[id={prompts.prompt_id(anchor.id)}]\nneed: {need}"
        )
        prompt = prompts.render_expander(
            SceneSnapshot.of(draft),
            engine.renderer(draft),
            draft.scenario,
            context=found,
            request=asked,
        )
        try:
            patch = await expander.run(prompt, deps)
        except UnexpectedModelBehavior as refused:
            # Recorded before the retry: an expansion that wrote nothing is the one the trace is
            # read for, and the Expander's own prompt and reason exist nowhere else.
            deps.expansions.record(prompt, f"no canon written: {refused}")
            raise ModelRetry(
                f"no canon could be written ({refused}). Plan this turn with what already exists."
            ) from refused
        deps.expansions.record(prompt, patch)
        # Outside the retry: the patch's own author already ran this sequence against a throwaway
        # draft, and a half-applied draft is not a state to plan another beat against.
        landed = transact(engine, draft, lambda copy: apply_patch(engine, copy, patch), deps.rng)
        deps.expansions.facts.extend(landed.facts)
        return written(patch)

    # One expansion at a time: two calls in one answer would interleave on the same draft, each
    # validating against a state without the other's canon.
    return FunctionToolset(tools=[Tool(expand_world, sequential=True)])


def advancement_stage(
    advancement: Advancement, settings: Settings
) -> Stage[AdvancementContext, ProposalBase]:
    def legal(ctx: RunContext[AdvancementContext], proposal: ProposalBase) -> ProposalBase:
        deps = ctx.deps
        refused = deps.advancement.violation(deps.state, deps.offer, proposal)
        if refused is not None:
            raise ModelRetry(refused)
        return proposal

    return Stage.of(
        "advisor",
        settings,
        instructions=f"{prompts.CORE_ADVISOR}\n\n{advancement.instructions}",
        output_type=NativeOutput(advancement.proposal_type),
        deps_type=AdvancementContext,
        validator=legal,
    )


def build_stages(
    engine: Engine[SheetBase], settings: Settings, source: CanonSource | None = None
) -> Stages:
    """A game with nothing to expand from builds no Expander, so its Director agent is the one
    shipped today."""
    expander: Stage[PlanContext, ExpansionPatch] | None = None
    expand_tool: FunctionToolset[PlanContext] | None = None
    if source is not None:
        expander = expander_stage(settings)
        expand_tool = expansion_toolset(engine, expander, source)
    return Stages(
        director=director_stage(engine, settings, expand_tool),
        narrator=narrator_stage(settings),
        worldkeeper=worldkeeper_stage(settings),
        expander=expander,
    )


def exchanges_to_messages(history: Sequence[Exchange]) -> list[ModelMessage]:
    messages: list[ModelMessage] = []
    for exchange in history:
        messages.append(ModelRequest(parts=[UserPromptPart(content=exchange.prompt)]))
        messages.append(ModelResponse(parts=[TextPart(content=exchange.narration)]))
    return messages
