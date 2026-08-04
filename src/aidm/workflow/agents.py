from collections.abc import Sequence
from dataclasses import dataclass
from functools import cached_property
from types import NoneType

from pydantic_ai import Agent, NativeOutput
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

from ..core.base import EntityDetail, Role
from ..core.config import ProviderConfig, RoleConfig, Settings
from ..core.engine import Engine
from ..core.tools import DirectorNotes, TurnContext, director_notes, world_toolset
from ..core.turn import Growth
from ..core.world import Exchange
from . import prompts


@dataclass(frozen=True)
class Stage[Deps, Out]:
    name: Role
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

    async def run(
        self,
        prompt: str,
        deps: Deps,
        recent: Sequence[ModelMessage] = (),
    ) -> Out:
        result = await self.agent.run(
            prompt,
            deps=deps,
            message_history=list(recent),
        )
        return result.output


@dataclass(frozen=True)
class SharedStages:
    narrator: Stage[None, str]
    maintainer: Stage[None, Growth]
    creator: Stage[None, EntityDetail]


type DirectorStage = Stage[TurnContext, DirectorNotes]


def director_stage(engine: Engine, settings: Settings) -> DirectorStage:
    role = settings.roles.director
    return Stage(
        name="director",
        instructions=f"{prompts.CORE_DIRECTOR}\n\n{engine.director_instructions}",
        output_type=NativeOutput(director_notes, name="DirectorNotes"),
        deps_type=TurnContext,
        role=role,
        provider=settings.providers.for_name(role.provider),
        toolsets=(world_toolset(), engine.director_toolset),
    )


def shared_stages(settings: Settings) -> SharedStages:
    narrator = settings.roles.narrator
    maintainer = settings.roles.maintainer
    creator = settings.roles.creator
    return SharedStages(
        narrator=Stage(
            name="narrator",
            instructions=prompts.NARRATOR,
            output_type=str,
            deps_type=NoneType,
            role=narrator,
            provider=settings.providers.for_name(narrator.provider),
        ),
        maintainer=Stage(
            name="maintainer",
            instructions=prompts.MAINTAINER,
            output_type=NativeOutput(Growth),
            deps_type=NoneType,
            role=maintainer,
            provider=settings.providers.for_name(maintainer.provider),
        ),
        creator=Stage(
            name="creator",
            instructions=prompts.CREATOR,
            output_type=NativeOutput(EntityDetail),
            deps_type=NoneType,
            role=creator,
            provider=settings.providers.for_name(creator.provider),
        ),
    )


def exchanges_to_messages(history: Sequence[Exchange]) -> list[ModelMessage]:
    messages: list[ModelMessage] = []
    for exchange in history:
        messages.append(ModelRequest(parts=[UserPromptPart(content=exchange.prompt)]))
        messages.append(ModelResponse(parts=[TextPart(content=exchange.narration)]))
    return messages
