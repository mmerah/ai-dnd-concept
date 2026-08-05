from collections.abc import Sequence
from dataclasses import dataclass
from functools import cached_property

from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.output import OutputSpec
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.toolsets import AbstractToolset

from ..core.config import ProviderConfig, RoleConfig, Settings
from ..core.world import Exchange


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
        return Agent(
            model,
            name=self.name,
            output_type=self.output_type,
            instructions=self.instructions,
            deps_type=self.deps_type,
            toolsets=list(self.toolsets),
            retries=self.role.retries,
            model_settings=OpenAIChatModelSettings(
                max_tokens=self.role.max_tokens,
                openai_reasoning_effort=self.role.reasoning_effort,
            ),
        )

    async def run(self, prompt: str, deps: Deps, recent: Sequence[ModelMessage] = ()) -> Out:
        output, _ = await self.converse(prompt, deps, recent)
        return output

    async def converse(
        self, prompt: str, deps: Deps, recent: Sequence[ModelMessage] = ()
    ) -> tuple[Out, list[ModelMessage]]:
        """`run`, keeping the conversation so a caller can continue it with a follow-up."""
        result = await self.agent.run(prompt, deps=deps, message_history=list(recent))
        return result.output, result.all_messages()


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
