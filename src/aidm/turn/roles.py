from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cached_property
from types import NoneType

from pydantic import ValidationError
from pydantic_ai import Agent, ModelRetry, NativeOutput, RunContext, TextOutput, ToolOutput
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.output import OutputSpec
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.toolsets import AbstractToolset

from aidm.config import ProviderConfig, RoleConfig, Settings
from aidm.engines.loader import Advancement, AdvancementOffer, Engine, ProposalBase
from aidm.state.plan import TurnPlanBase
from aidm.state.turn import SceneDirective, WorldkeeperReport
from aidm.state.world import Exchange, GameState

from . import prompts


class ChannelSafeModel(WrapperModel):
    """gpt-oss models sometimes append their harmony channel marker to a tool call's name
    (`turn_plan<|channel|>json`); the call is otherwise well-formed, so strip the marker."""

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        response = await super().request(messages, model_settings, model_request_parameters)
        for part in response.parts:
            if type(part) is ToolCallPart and "<|" in part.tool_name:
                part.tool_name = part.tool_name.split("<|", 1)[0]
        return response


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
        model = ChannelSafeModel(OpenAIChatModel(self.role.model, provider=provider))
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


def stage[Deps, Out](
    name: str,
    settings: Settings,
    *,
    instructions: str,
    output_type: OutputSpec[Out],
    deps_type: type[Deps],
    toolsets: Sequence[AbstractToolset[Deps]] = (),
    validator: Callable[[RunContext[Deps], Out], Out] | None = None,
) -> Stage[Deps, Out]:
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
    """What the Director's output validator judges a plan against: the untouched committed state."""

    engine: Engine
    state: GameState


@dataclass(frozen=True, slots=True)
class AdvisorContext:
    advancement: Advancement
    state: GameState
    offer: AdvancementOffer


@dataclass(frozen=True, slots=True)
class Stages:
    """The turn's model-facing roles, built once per session."""

    scene: Stage[GameState, SceneDirective]
    director: Stage[PlanContext, TurnPlanBase]
    narrator: Stage[None, str]
    worldkeeper: Stage[None, WorldkeeperReport]


def scene_stage(settings: Settings) -> Stage[GameState, SceneDirective]:
    def known(ctx: RunContext[GameState], directive: SceneDirective) -> SceneDirective:
        state = ctx.deps
        missing = sorted(set(directive.threads) - set(state.world.threads))
        if missing:
            raise ModelRetry(f"no such thread: {', '.join(missing)}")
        # A `reveal` naming anything but an unmet entity renders nothing
        unmet = {entity.id for entity in state.world.entities.values() if not entity.known}
        wrong = sorted(set(directive.reveal) - unmet)
        if wrong:
            raise ModelRetry(f"not something the player has yet to find: {', '.join(wrong)}")
        if fault := prompts.check_speaker(prompts.SceneSnapshot.of(state), directive.speaker_id):
            raise ModelRetry(fault)
        return directive

    return stage(
        "scene",
        settings,
        instructions=prompts.SCENE_DIRECTOR,
        output_type=NativeOutput(SceneDirective),
        deps_type=GameState,
        validator=known,
    )


def director_stage(engine: Engine, settings: Settings) -> Stage[PlanContext, TurnPlanBase]:
    def legal(ctx: RunContext[PlanContext], plan: TurnPlanBase) -> TurnPlanBase:
        deps = ctx.deps
        refused = deps.engine.check_plan(deps.state, plan)
        if refused is not None:
            raise ModelRetry(refused)
        return plan

    return stage(
        "director",
        settings,
        instructions=f"{prompts.RULES_DIRECTOR}\n\n{engine.director_instructions}",
        output_type=[
            ToolOutput(engine.plan_type, name="turn_plan"),
            TextOutput(plan_from_text(engine.plan_type)),
        ],
        deps_type=PlanContext,
        toolsets=engine.director_toolsets,
        validator=legal,
    )


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


def advisor(advancement: Advancement, settings: Settings) -> Stage[AdvisorContext, ProposalBase]:
    def legal(ctx: RunContext[AdvisorContext], proposal: ProposalBase) -> ProposalBase:
        deps = ctx.deps
        refused = deps.advancement.violation(deps.state, deps.offer, proposal)
        if refused is not None:
            raise ModelRetry(refused)
        return proposal

    return stage(
        "advisor",
        settings,
        instructions=f"{prompts.CORE_ADVISOR}\n\n{advancement.instructions}",
        output_type=NativeOutput(advancement.proposal_type),
        deps_type=AdvisorContext,
        validator=legal,
    )


def build_stages(engine: Engine, settings: Settings) -> Stages:
    return Stages(
        scene=scene_stage(settings),
        director=director_stage(engine, settings),
        narrator=narrator_stage(settings),
        worldkeeper=worldkeeper_stage(settings),
    )


def plan_from_text(plan_type: type[TurnPlanBase]) -> Callable[[str], TurnPlanBase]:
    """gpt-oss sometimes answers the Director in plain text instead of calling `turn_plan`."""

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


def exchanges_to_messages(history: Sequence[Exchange]) -> list[ModelMessage]:
    messages: list[ModelMessage] = []
    for exchange in history:
        messages.append(ModelRequest(parts=[UserPromptPart(content=exchange.prompt)]))
        messages.append(ModelResponse(parts=[TextPart(content=exchange.narration)]))
    return messages
