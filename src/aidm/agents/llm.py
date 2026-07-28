from collections.abc import Callable, Sequence
from functools import cache
from types import NoneType

from pydantic_ai import Agent
from pydantic_ai._output import OutputValidatorFunc  # pyright: ignore[reportPrivateImportUsage]
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.output import OutputSpec
from pydantic_ai.providers.openai import OpenAIProvider

from ..config import ProviderName, settings
from ..domain.models import Role


@cache
def _provider(name: ProviderName) -> OpenAIProvider:
    conf = settings().providers.for_name(name)
    return OpenAIProvider(base_url=conf.base_url, api_key=conf.api_key.get_secret_value())


@cache
def model(role: Role) -> OpenAIChatModel:
    """Defer provider setup so importing roles needs no API key."""
    conf = settings().roles.for_role(role)
    return OpenAIChatModel(conf.model, provider=_provider(conf.provider))


def build_agent[Deps, Out](
    name: Role,
    *,
    output_type: OutputSpec[Out],
    instructions: str,
    deps_type: type[Deps] = NoneType,
    output_validators: Sequence[OutputValidatorFunc[Deps, Out]] = (),
) -> Callable[[], Agent[Deps, Out]]:
    """Return a cached accessor so tests can override agents before first use."""

    @cache
    def agent() -> Agent[Deps, Out]:
        conf = settings().roles.for_role(name)
        built = Agent(
            model(name),
            name=name,
            output_type=output_type,
            instructions=instructions,
            deps_type=deps_type,
            retries=conf.retries,
            model_settings=OpenAIChatModelSettings(
                max_tokens=conf.max_tokens,
                openai_reasoning_effort=conf.reasoning_effort,
            ),
        )
        for validator in output_validators:
            built.output_validator(validator)
        return built

    return agent
