from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache, cached_property
from types import NoneType

from pydantic_ai import Agent, NativeOutput
from pydantic_ai._output import OutputValidatorFunc  # pyright: ignore[reportPrivateImportUsage]
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.output import OutputSpec
from pydantic_ai.providers.openai import OpenAIProvider

from ..config import ProviderName, settings
from ..domain.models.base import Role
from ..domain.models.direction import Direction
from ..domain.models.entities import EntityDetail, Growth
from . import instructions
from .context import Scene
from .director import validate_ids


@cache
def _provider(name: ProviderName) -> OpenAIProvider:
    conf = settings().providers.for_name(name)
    return OpenAIProvider(base_url=conf.base_url, api_key=conf.api_key.get_secret_value())


@cache
def _model(role: Role) -> OpenAIChatModel:
    """Defer provider setup so importing a stage needs no API key."""
    conf = settings().roles.for_role(role)
    return OpenAIChatModel(conf.model, provider=_provider(conf.provider))


@dataclass(frozen=True)
class Stage[Deps, Out]:
    name: Role
    instructions: str
    output_type: OutputSpec[Out]
    deps_type: type[Deps]
    validators: tuple[OutputValidatorFunc[Deps, Out], ...] = ()

    @cached_property
    def agent(self) -> Agent[Deps, Out]:
        """Built lazily so a test can override the model before the first run."""
        conf = settings().roles.for_role(self.name)
        built = Agent(
            _model(self.name),
            name=self.name,
            output_type=self.output_type,
            instructions=self.instructions,
            deps_type=self.deps_type,
            retries=conf.retries,
            model_settings=OpenAIChatModelSettings(
                max_tokens=conf.max_tokens,
                openai_reasoning_effort=conf.reasoning_effort,
            ),
        )
        for validator in self.validators:
            built.output_validator(validator)
        return built

    async def run(self, prompt: str, deps: Deps, recent: Sequence[ModelMessage] = ()) -> Out:
        return (await self.agent.run(prompt, deps=deps, message_history=list(recent))).output


DIRECTOR = Stage(
    name="director",
    instructions=instructions.DIRECTOR,
    output_type=NativeOutput(Direction),
    deps_type=Scene,
    validators=(validate_ids,),
)

NARRATOR = Stage(
    name="narrator",
    instructions=instructions.NARRATOR,
    output_type=str,
    deps_type=NoneType,
)

MAINTAINER = Stage(
    name="maintainer",
    instructions=instructions.MAINTAINER,
    output_type=NativeOutput(Growth),
    deps_type=NoneType,
)

CREATOR = Stage(
    name="creator",
    instructions=instructions.CREATOR,
    output_type=NativeOutput(EntityDetail),
    deps_type=NoneType,
)
