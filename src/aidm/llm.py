import json
import logging
from collections.abc import Callable, Sequence

from pydantic import BaseModel, JsonValue
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.output import OutputSpec
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import GenerateToolJsonSchema
from pydantic_ai.toolsets import AbstractToolset

from aidm.config import Role, Settings

LOGGER = logging.getLogger(__name__)


def schema_of(args: type[BaseModel]) -> dict[str, JsonValue]:
    """One schema function, so what MCP publishes is what the agent is offered."""
    schema = args.model_json_schema(schema_generator=GenerateToolJsonSchema)
    # The tool already names itself; the argument class name would be a second, wrong name.
    schema.pop("title", None)
    return schema


def _object(text: str) -> bool:
    try:
        return isinstance(json.loads(text), dict)
    except ValueError:
        return False


def _unfenced(args: str) -> str:
    text = args.strip()
    return text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()


def _unwrapped(args: str) -> str:
    """Arguments encoded twice: a JSON string whose content is the object."""
    try:
        inner = json.loads(args)
    except ValueError:
        return args
    return inner if isinstance(inner, str) else args


def _closed(args: str) -> str:
    """Arguments cut short: whatever is still open at the end is closed, trailing comma dropped."""
    closers: list[str] = []
    in_string = escaped = False
    for char in args:
        if escaped:
            escaped = False
        elif in_string:
            escaped, in_string = char == "\\", char != '"'
        elif char == '"':
            in_string = True
        elif char in "{[":
            closers.append("}" if char == "{" else "]")
        elif char in "}]" and closers:
            _ = closers.pop()
    head = args + '"' if in_string else args.rstrip().removesuffix(",")
    return head + "".join(reversed(closers))


def repaired(args: str) -> str:
    """Repair unambiguous object arguments and otherwise preserve them exactly."""
    text = args
    for fix in (_unfenced, _unwrapped, _closed):
        if _object(text):
            return text
        text = fix(text)
    return text if _object(text) else args


class RepairedToolArgs(WrapperModel):
    """Repair malformed gpt-oss tool arguments that model retries repeat unchanged."""

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        response = await self.wrapped.request(messages, model_settings, model_request_parameters)
        for part in response.parts:
            if isinstance(part, ToolCallPart) and isinstance(part.args, str):
                fixed = repaired(part.args)
                if fixed != part.args:
                    LOGGER.warning("repaired broken arguments for tool %s", part.tool_name)
                    part.args = fixed
        return response


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
    model = RepairedToolArgs(OpenAIChatModel(role_config.model, provider=provider))
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
