import logging
from asyncio import timeout
from collections.abc import Sequence
from dataclasses import dataclass
from time import monotonic
from typing import Literal, Protocol

from httpx import HTTPError, HTTPStatusError
from pydantic import BaseModel, ConfigDict, JsonValue

from aidm.app.providers import post_bearer
from aidm.app.spawn import RunResult, final_message
from aidm.config import ProviderConfig, Role, RoleConfig, Settings
from aidm.core.entities import Loose, Refusal, parse
from aidm.core.io import decode
from aidm.core.model import AnyGame
from aidm.core.tools import MasterTool, schema_of

LOGGER = logging.getLogger(__name__)


class Tools(Protocol):
    def published_tools(self) -> Sequence[MasterTool[AnyGame]]: ...
    def call(self, name: str, raw: JsonValue) -> str: ...


class _Echoed(BaseModel):
    """Kept whole: a reply goes back in the next request, reasoning and all."""

    model_config = ConfigDict(extra="allow", frozen=True)


class _Function(_Echoed):
    name: str
    arguments: str


class _ToolCall(_Echoed):
    id: str
    type: Literal["function"]
    function: _Function


class _Said(_Echoed):
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


@dataclass(frozen=True, slots=True)
class BuiltinSpawner:
    settings: Settings
    tools: Tools

    async def run(self, role: Role, prompt: str, session: str | None) -> RunResult:
        """Stateless, so `session` is never given back: a retry resends the whole prompt."""
        config = self.settings.roles.for_name(role)
        if config.api is None:
            raise ValueError(f"the {role} is played by the {config.provider!r} CLI")
        provider = self.settings.providers.for_name(config.api)
        published = self.tools.published_tools() if role == "master" else ()
        started = monotonic()
        try:
            async with timeout(config.timeout):
                said, rounds = await self._converse(role, config, provider, prompt, published)
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
        self,
        role: Role,
        config: RoleConfig,
        provider: ProviderConfig,
        prompt: str,
        published: Sequence[MasterTool[AnyGame]],
    ) -> tuple[str, int]:
        messages: list[JsonValue] = [{"role": "user", "content": prompt}]
        tools: list[JsonValue] = [_declared(tool) for tool in published]
        for rounds in range(1, config.max_rounds + 1):
            said = await _complete(config, provider, messages, tools)
            messages.append(said.model_dump(mode="json", exclude_none=True))
            if not said.tool_calls:
                return said.content or "", rounds
            if not tools:
                called = said.tool_calls[0].function.name
                raise Refusal(f"the {role} has no tools, yet called {called!r}")
            for call in said.tool_calls:
                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": self._answer(call)}
                )
        raise Refusal(
            f"the {role} made {config.max_rounds} rounds of tool calls without ending the turn"
        )

    def _answer(self, call: _ToolCall) -> str:
        """What the server does: a refusal is the result the model reads and carries on from."""
        try:
            return self.tools.call(call.function.name, decode(call.function.arguments))
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
