from asyncio import Event, Lock, Task, create_task
from dataclasses import dataclass, field

import mcp_types as types
from mcp.server import Server, ServerRequestContext
from mcp.server.streamable_http_manager import StreamableHTTPASGIApp, StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings

from aidm.app.runtime import Runtime
from aidm.core.entities import Refusal
from aidm.core.tools import schema_of

SERVER_NAME = "aidm"
MOUNT_PATH = "/mcp"


@dataclass(slots=True)
class MountedLifespan:
    """A mounted app's lifespan never runs; anyio needs one task to enter and exit the manager."""

    manager: StreamableHTTPSessionManager
    _ready: Event = field(default_factory=Event)
    _stopping: Event = field(default_factory=Event)
    _serving: Task[None] | None = None

    async def start(self) -> None:
        self._serving = create_task(self._serve())
        await self._ready.wait()
        if self._serving.done():
            self._serving.result()

    async def stop(self) -> None:
        self._stopping.set()
        if self._serving is not None:
            await self._serving

    async def _serve(self) -> None:
        try:
            async with self.manager.run():
                self._ready.set()
                await self._stopping.wait()
        finally:
            # Set on failure too, or a manager that never came up would hang the startup.
            self._ready.set()


def endpoint(
    runtime: Runtime,
) -> tuple[StreamableHTTPASGIApp, StreamableHTTPSessionManager]:
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
    lock = Lock()

    async def on_list_tools(
        _ctx: ServerRequestContext[dict[str, object]],
        _params: types.PaginatedRequestParams | None,
    ) -> types.ListToolsResult:
        return types.ListToolsResult(
            tools=[
                types.Tool(
                    name=tool.name,
                    description=tool.description,
                    input_schema=schema_of(tool.args),
                )
                for tool in runtime.published_tools()
            ]
        )

    async def on_call_tool(
        _ctx: ServerRequestContext[dict[str, object]], params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        """The lock replaces a sequential toolset: a CLI may call several tools at once."""
        async with lock:
            try:
                answered = runtime.call(params.name, params.arguments or {})
            except Refusal as refused:
                return _content(str(refused), error=True)
        return _content(answered)

    return Server(SERVER_NAME, on_list_tools=on_list_tools, on_call_tool=on_call_tool)


def _content(body: str, *, error: bool = False) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(text=body)], is_error=error)
