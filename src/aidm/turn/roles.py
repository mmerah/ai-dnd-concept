from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cached_property
from types import NoneType

from pydantic_ai import Agent, ModelRetry, NativeOutput, RunContext
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.output import OutputSpec
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.toolsets import AbstractToolset

from aidm.config import ProviderConfig, Role, RoleConfig, Settings
from aidm.engines.advancement import Advancement, Offer, ProposalBase
from aidm.engines.loader import Engine
from aidm.engines.sheets import SheetBase
from aidm.state.plan import DirectorBeat
from aidm.state.turn import WorldkeeperReport
from aidm.state.world import Exchange, GameState

from . import prompts


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
    """What the Director's output validator judges against: the state the answer will be resolved
    against — the committed state for the turn's plan, the turn's own draft for a later beat."""

    engine: Engine[SheetBase]
    state: GameState
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
    narrator: Stage[None, str]
    worldkeeper: Stage[GameState, WorldkeeperReport]


def director_stage(
    engine: Engine[SheetBase], settings: Settings
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

    return Stage.of(
        "director",
        settings,
        instructions=f"{prompts.DIRECTOR}\n\n{engine.director_instructions}",
        output_type=NativeOutput(DirectorBeat),
        deps_type=PlanContext,
        toolsets=engine.director_toolsets,
        validator=legal,
    )


def narrator_stage(settings: Settings) -> Stage[None, str]:
    return Stage.of(
        "narrator", settings, instructions=prompts.NARRATOR, output_type=str, deps_type=NoneType
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


def build_stages(engine: Engine[SheetBase], settings: Settings) -> Stages:
    return Stages(
        director=director_stage(engine, settings),
        narrator=narrator_stage(settings),
        worldkeeper=worldkeeper_stage(settings),
    )


def exchanges_to_messages(history: Sequence[Exchange]) -> list[ModelMessage]:
    messages: list[ModelMessage] = []
    for exchange in history:
        messages.append(ModelRequest(parts=[UserPromptPart(content=exchange.prompt)]))
        messages.append(ModelResponse(parts=[TextPart(content=exchange.narration)]))
    return messages
