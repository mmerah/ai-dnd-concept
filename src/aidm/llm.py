from collections.abc import Callable, Sequence

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.output import OutputSpec
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.toolsets import AbstractToolset

from aidm.config import Role, Settings


def build_agent[Deps, Out](
    role: Role,
    settings: Settings,
    *,
    instructions: str,
    output_type: OutputSpec[Out],
    deps_type: type[Deps],
    toolsets: Sequence[AbstractToolset[Deps]] = (),
    validator: Callable[[RunContext[Deps], Out], Out] | None = None,
) -> Agent[Deps, Out]:
    role_config = settings.role(role)
    provider_config = settings.providers.for_name(role_config.provider)
    provider = OpenAIProvider(
        base_url=provider_config.base_url,
        api_key=provider_config.api_key.get_secret_value(),
    )
    model = OpenAIChatModel(role_config.model, provider=provider)
    model_settings = OpenAIChatModelSettings(
        max_tokens=role_config.max_tokens,
        openai_reasoning_effort=role_config.reasoning_effort,
    )
    if role_config.temperature is not None:
        model_settings["temperature"] = role_config.temperature
    agent = Agent(
        model,
        name=role,
        output_type=output_type,
        instructions=instructions,
        deps_type=deps_type,
        toolsets=list(toolsets),
        retries=role_config.retries,
        model_settings=model_settings,
    )
    if validator is not None:
        _ = agent.output_validator(validator)
    return agent
