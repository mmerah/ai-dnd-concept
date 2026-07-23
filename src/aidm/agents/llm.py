"""The only place that knows about the model provider, and the one builder every role shares."""

from collections.abc import Callable, Sequence
from functools import cache
from types import NoneType

from pydantic_ai import Agent
from pydantic_ai._output import OutputValidatorFunc  # pyright: ignore[reportPrivateImportUsage]
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.output import OutputSpec
from pydantic_ai.providers.openai import OpenAIProvider

from ..config import settings

RETRIES = 3  # small models mis-name things; let them be corrected instead of failing the turn


@cache
def model() -> OpenAIChatModel:
    """Deferred so importing a role never needs an API key."""
    conf = settings()
    provider = OpenAIProvider(base_url=conf.ai_base_url, api_key=conf.ai_api_key)
    return OpenAIChatModel(conf.ai_model, provider=provider)


def build_agent[Deps, Out](
    name: str,
    *,
    output_type: OutputSpec[Out],
    instructions: str,
    deps_type: type[Deps] = NoneType,
    output_validators: Sequence[OutputValidatorFunc[Deps, Out]] = (),
) -> Callable[[], Agent[Deps, Out]]:
    """One wiring of `model()` + `RETRIES` for every role. Returns a cached accessor, so
    `role.agent()` keeps working, tests can `.override(model=...)`, and `model()` stays deferred."""

    @cache
    def agent() -> Agent[Deps, Out]:
        built = Agent(
            model(),
            name=name,
            output_type=output_type,
            instructions=instructions,
            deps_type=deps_type,
            retries=RETRIES,
        )
        for validator in output_validators:
            built.output_validator(validator)
        return built

    return agent
