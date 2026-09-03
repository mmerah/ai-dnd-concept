import mcp_types as types
from mcp.server import Server, ServerRequestContext
from mcp.server.streamable_http_manager import StreamableHTTPASGIApp, StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import JsonValue, TypeAdapter

from aidm.app.runtime import Runtime
from aidm.core.entities import Refusal
from aidm.core.model import AnyGame
from aidm.core.tools import MasterTool, schema_of
from aidm.turn.run import NO_TURN

SERVER_NAME = "aidm"
MOUNT_PATH = "/mcp"

_ARGUMENTS = TypeAdapter(dict[str, JsonValue])


def list_tools(runtime: Runtime) -> list[types.Tool]:
    return [_published(one) for one in runtime.published_tools()]


def call(runtime: Runtime, name: str, raw: dict[str, JsonValue]) -> str:
    session = runtime.playing()
    turn = None if session is None else session.turn
    if turn is None:
        raise Refusal(NO_TURN)
    return turn.call(name, raw)


def endpoint(
    runtime: Runtime,
) -> tuple[StreamableHTTPASGIApp, StreamableHTTPSessionManager]:
    """The transport, served from the running app so the spawned CLI reaches the live game."""
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
    return StreamableHTTPASGIApp(manager), manager


def _build_server(runtime: Runtime) -> Server[dict[str, object]]:
    async def on_list_tools(
        _ctx: ServerRequestContext[dict[str, object]],
        _params: types.PaginatedRequestParams | None,
    ) -> types.ListToolsResult:
        return types.ListToolsResult(tools=list_tools(runtime))

    async def on_call_tool(
        _ctx: ServerRequestContext[dict[str, object]], params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        """The lock replaces a sequential toolset: a CLI may call several tools at once."""
        async with runtime.lock:
            try:
                answered = call(
                    runtime, params.name, _ARGUMENTS.validate_python(params.arguments or {})
                )
            except Refusal as refused:
                return _content(str(refused), error=True)
        return _content(answered)

    return Server(SERVER_NAME, on_list_tools=on_list_tools, on_call_tool=on_call_tool)


def _published(tool: MasterTool[AnyGame]) -> types.Tool:
    return types.Tool(
        name=tool.name, description=tool.description, input_schema=schema_of(tool.args)
    )


def _content(body: str, error: bool = False) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(text=body)], is_error=error)
