from contextlib import AsyncExitStack
from dataclasses import dataclass

import mcp_types as types
from mcp.server import Server, ServerRequestContext
from mcp.server.streamable_http_manager import StreamableHTTPASGIApp, StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import JsonValue, TypeAdapter

from aidm.app.runtime import NO_TURN, SERVER_TOOLS, Runtime, ServerTool
from aidm.core.entities import require_unique
from aidm.core.tools import MasterTool, NoArgs, schema_of

SERVER_NAME = "aidm"
MOUNT_PATH = "/mcp"

_ARGUMENTS = TypeAdapter(dict[str, JsonValue])


@dataclass(frozen=True, slots=True)
class Endpoint:
    """The transport, served from the running app so the spawned CLI reaches the live game."""

    asgi: StreamableHTTPASGIApp
    # A mounted app's own lifespan never runs, so the manager's task group is opened by hand.
    running: AsyncExitStack
    manager: StreamableHTTPSessionManager

    async def open(self) -> None:
        _ = await self.running.enter_async_context(self.manager.run())

    async def close(self) -> None:
        await self.running.aclose()


def offered(runtime: Runtime) -> list[types.Tool]:
    engine_tools = runtime.engine.tools
    # `call` reaches the server's own tools first, so a shared name would shadow the engine's.
    names = (*(one.name for one in SERVER_TOOLS), *(one.name for one in engine_tools))
    require_unique("published tool names", names)
    return [_published(one) for one in (*SERVER_TOOLS, *engine_tools)]


def call(runtime: Runtime, name: str, raw: dict[str, JsonValue]) -> str:
    session = runtime.playing()
    if session is None:
        raise ValueError(NO_TURN)
    return session.call_tool(name, raw)


def endpoint(runtime: Runtime) -> Endpoint:
    manager = StreamableHTTPSessionManager(
        app=_build_server(runtime),
        json_response=True,
        stateless=True,
        security_settings=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["127.0.0.1:*", "localhost:*"],
            allowed_origins=["http://127.0.0.1:*", "http://localhost:*"],
        ),
    )
    return Endpoint(asgi=StreamableHTTPASGIApp(manager), running=AsyncExitStack(), manager=manager)


def _build_server(runtime: Runtime) -> Server[dict[str, object]]:
    async def on_list_tools(
        ctx: ServerRequestContext[dict[str, object]], params: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        del ctx, params
        return types.ListToolsResult(tools=offered(runtime))

    async def on_call_tool(
        ctx: ServerRequestContext[dict[str, object]], params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        """The lock replaces a sequential toolset: a CLI may call several tools at once."""
        del ctx
        async with runtime.lock:
            try:
                answered = call(
                    runtime, params.name, _ARGUMENTS.validate_python(params.arguments or {})
                )
            except ValueError as refused:
                return _content(str(refused), error=True)
        return _content(answered)

    return Server(SERVER_NAME, on_list_tools=on_list_tools, on_call_tool=on_call_tool)


def _published(tool: ServerTool | MasterTool) -> types.Tool:
    args = NoArgs if isinstance(tool, ServerTool) else tool.args
    return types.Tool(name=tool.name, description=tool.description, input_schema=schema_of(args))


def _content(body: str, error: bool = False) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(text=body)], is_error=error)
