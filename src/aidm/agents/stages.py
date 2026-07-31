from collections.abc import Sequence
from dataclasses import dataclass
from functools import cached_property
from types import NoneType

from pydantic import BaseModel
from pydantic_ai import Agent, NativeOutput
from pydantic_ai._output import OutputValidatorFunc  # pyright: ignore[reportPrivateImportUsage]
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.output import OutputSpec
from pydantic_ai.providers.openai import OpenAIProvider

from ..config import ProviderConfig, RoleConfig, Settings
from ..domain.base import Role
from ..domain.entities import EntityDetail
from ..domain.growth import Growth
from ..engine_api.contracts import RulesEngine
from . import instructions
from .context import DirectorScene


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


def director_stage(
    engine: RulesEngine,
    settings: Settings,
) -> Stage[DirectorScene, BaseModel]:
    role = settings.roles.director
    return Stage(
        name="director",
        instructions=f"{instructions.CORE_DIRECTOR}\n\n{engine.director.instructions()}",
        output_type=engine.director.output,
        deps_type=DirectorScene,
        role=role,
        provider=settings.providers.for_name(role.provider),
        validators=(engine.director.validate,),
    )


def shared_stages(settings: Settings) -> SharedStages:
    narrator = settings.roles.narrator
    maintainer = settings.roles.maintainer
    creator = settings.roles.creator
    return SharedStages(
        narrator=Stage(
            name="narrator",
            instructions=instructions.NARRATOR,
            output_type=str,
            deps_type=NoneType,
            role=narrator,
            provider=settings.providers.for_name(narrator.provider),
        ),
        maintainer=Stage(
            name="maintainer",
            instructions=instructions.MAINTAINER,
            output_type=NativeOutput(Growth),
            deps_type=NoneType,
            role=maintainer,
            provider=settings.providers.for_name(maintainer.provider),
        ),
        creator=Stage(
            name="creator",
            instructions=instructions.CREATOR,
            output_type=NativeOutput(EntityDetail),
            deps_type=NoneType,
            role=creator,
            provider=settings.providers.for_name(creator.provider),
        ),
    )
