import logging
from asyncio import timeout
from time import monotonic
from typing import Literal

from httpx import HTTPError, HTTPStatusError
from pydantic import JsonValue

from aidm.app.providers import post_bearer
from aidm.app.spawn import RunResult, Tools, final_message
from aidm.config import ProviderConfig, Role, RoleConfig
from aidm.core.entities import Echoed, Loose, Refusal, parse
from aidm.core.io import decode
from aidm.core.model import AnyGame
from aidm.core.tools import MasterTool, schema_of

LOGGER = logging.getLogger(__name__)


class _Function(Echoed):
    name: str
    arguments: str


class _ToolCall(Echoed):
    id: str
    type: Literal["function"]
    function: _Function


class _Said(Echoed):
    role: Literal["assistant"]
    content: str | None = None
    tool_calls: tuple[_ToolCall, ...] | None = None


class _Choice(Loose):
    message: _Said


class _Error(Loose):
    message: str


class _Completion(Loose):
    choices: tuple[_Choice, ...] = ()
    error: _Error | None = None


async def run_builtin(
    role: Role, config: RoleConfig, provider: ProviderConfig, prompt: str, tools: Tools | None
) -> RunResult:
    """Stateless: nothing is ever resumed, and a retry resends the whole prompt."""
    started = monotonic()
    try:
        async with timeout(config.timeout):
            said, rounds = await _converse(role, config, provider, prompt, tools)
    except TimeoutError:
        raise Refusal(f"the {role} answered nothing in {config.timeout:.0f}s") from None
    except HTTPError as failed:
        raise Refusal(f"the {role}'s provider failed: {_detail(failed)}") from failed
    LOGGER.info(
        "%s answered: provider=%s model=%s effort=%s in %d rounds and %.1fs",
        role,
        config.provider,
        config.model,
        config.effort,
        rounds,
        monotonic() - started,
    )
    return RunResult(final_message(said), None)


async def _converse(
    role: Role, config: RoleConfig, provider: ProviderConfig, prompt: str, tools: Tools | None
) -> tuple[str, int]:
    messages: list[JsonValue] = [{"role": "user", "content": prompt}]
    published: list[JsonValue] = (
        [] if tools is None else [_declared(tool) for tool in tools.published_tools()]
    )
    for rounds in range(1, config.max_rounds + 1):
        said = await _complete(config, provider, messages, published)
        messages.append(said.model_dump(mode="json", exclude_none=True))
        if not said.tool_calls:
            return said.content or "", rounds
        if tools is None:
            called = said.tool_calls[0].function.name
            raise Refusal(f"the {role} has no tools, yet called {called!r}")
        for call in said.tool_calls:
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": _answer(tools, call)}
            )
    raise Refusal(
        f"the {role} made {config.max_rounds} rounds of tool calls without ending the turn"
    )


def _answer(tools: Tools, call: _ToolCall) -> str:
    """What the server does: a refusal is the result the model reads and carries on from."""
    try:
        return tools.call(call.function.name, decode(call.function.arguments))
    except Refusal as refused:
        return str(refused)


async def _complete(
    config: RoleConfig, provider: ProviderConfig, messages: list[JsonValue], tools: list[JsonValue]
) -> _Said:
    body: dict[str, JsonValue] = {
        "model": config.model,
        "messages": messages,
        "reasoning_effort": config.effort,
    }
    if tools:
        body["tools"] = tools
    raw = await post_bearer(provider, "/chat/completions", body, config.timeout)
    reply = parse(_Completion, decode(raw.decode(errors="replace")))
    if reply.error is not None:
        raise Refusal(f"the provider answered an error: {reply.error.message}")
    if not reply.choices:
        raise Refusal("the provider answered no choices")
    return reply.choices[0].message


def _declared(tool: MasterTool[AnyGame]) -> JsonValue:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": schema_of(tool.args),
        },
    }


def _detail(failed: HTTPError) -> str:
    if isinstance(failed, HTTPStatusError):
        return f"{failed.response.status_code}: {failed.response.text[-500:]}"
    return str(failed)
