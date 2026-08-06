from collections.abc import Sequence
from dataclasses import dataclass
from functools import cached_property

from pydantic_ai import Agent
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
from aidm.state.world import Exchange


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
) -> Stage[Deps, Out]:
    role = settings.role(name)
    return Stage(
        name=name,
        instructions=instructions,
        output_type=output_type,
        deps_type=deps_type,
        role=role,
        provider=settings.providers.for_name(role.provider),
        toolsets=toolsets,
    )


def exchanges_to_messages(history: Sequence[Exchange]) -> list[ModelMessage]:
    messages: list[ModelMessage] = []
    for exchange in history:
        messages.append(ModelRequest(parts=[UserPromptPart(content=exchange.prompt)]))
        messages.append(ModelResponse(parts=[TextPart(content=exchange.narration)]))
    return messages
