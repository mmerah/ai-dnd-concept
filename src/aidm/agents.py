from collections.abc import Sequence
from dataclasses import dataclass
from functools import cached_property
from types import NoneType

from pydantic import BaseModel
from pydantic_ai import Agent, NativeOutput
from pydantic_ai._output import OutputValidatorFunc  # pyright: ignore[reportPrivateImportUsage]
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

from aidm.engines.dnd5e.direction import Dnd5eDirection
from aidm.engines.dnd5e.engine import Dnd5eEngine
from aidm.engines.story.direction import StoryDirection
from aidm.engines.story.engine import StoryEngine

from . import prompts
from .base import EntityDetail, Role
from .config import ProviderConfig, RoleConfig, Settings
from .engine import Engine
from .growth import Growth
from .world import Exchange, GameState


@dataclass(frozen=True)
class Stage[Deps, Out]:
    name: Role
    instructions: str
    output_type: OutputSpec[Out]
    deps_type: type[Deps]
    role: RoleConfig
    provider: ProviderConfig
    validators: tuple[OutputValidatorFunc[Deps, Out], ...] = ()

    @cached_property
    def agent(self) -> Agent[Deps, Out]:
        provider = OpenAIProvider(
            base_url=self.provider.base_url,
            api_key=self.provider.api_key.get_secret_value(),
        )
        model = OpenAIChatModel(self.role.model, provider=provider)
        built = Agent(
            model,
            name=self.name,
            output_type=self.output_type,
            instructions=self.instructions,
            deps_type=self.deps_type,
            retries=self.role.retries,
            model_settings=OpenAIChatModelSettings(
                max_tokens=self.role.max_tokens,
                openai_reasoning_effort=self.role.reasoning_effort,
            ),
        )
        for validator in self.validators:
            built.output_validator(validator)
        return built

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


type DirectorStage = Stage[GameState, StoryDirection] | Stage[GameState, Dnd5eDirection]


def director_stage(engine: Engine, settings: Settings) -> DirectorStage:
    """One branch per engine so the director's own direction type flows through the stage."""
    match engine:
        case StoryEngine(director=director):
            return _director_stage(
                director.instructions(), director.output, director.validate, settings
            )
        case Dnd5eEngine(director=director):
            return _director_stage(
                director.instructions(), director.output, director.validate, settings
            )


def _director_stage[D: BaseModel](
    mechanics: str,
    output: OutputSpec[D],
    validate: OutputValidatorFunc[GameState, D],
    settings: Settings,
) -> Stage[GameState, D]:
    role = settings.roles.director
    return Stage(
        name="director",
        instructions=f"{prompts.CORE_DIRECTOR}\n\n{mechanics}",
        output_type=output,
        deps_type=GameState,
        role=role,
        provider=settings.providers.for_name(role.provider),
        validators=(validate,),
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
