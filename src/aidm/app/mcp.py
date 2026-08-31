from collections.abc import Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass

import mcp_types as types
from mcp.server import Server, ServerRequestContext
from mcp.server.streamable_http_manager import StreamableHTTPASGIApp, StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter

from aidm.app.runtime import NO_TURN, GameService, Runtime
from aidm.state.entities import Frozen, require_unique
from aidm.state.tools import DirectorTool, NoArgs, schema_of
from aidm.turn.run import Turn

SERVER_NAME = "aidm"
MOUNT_PATH = "/mcp"
START_FIRST = "call `start_turn` first: it opens the turn and hands back the picture."
ALREADY_OPEN = "the turn is already open. `scene` gives the picture back."
DECIDING = "the rules are waiting on the player; the scene after this one waits with them."

_ARGUMENTS = TypeAdapter(dict[str, JsonValue])


class NextScene(Frozen):
    # Without this the field docstrings below never reach the schema the model reads.
    model_config = ConfigDict(use_attribute_docstrings=True)

    intent: str = Field(min_length=1)
    """What comes next, in one or two sentences: where the story goes and what is at stake."""
    include: tuple[str, ...] = ()
    """Ids of cast the next scene should bring back. A hint, not an order."""


@dataclass(frozen=True, slots=True)
class ServerTool:
    """What is published is what is run: one place for the name, the schema and the behaviour."""

    name: str
    description: str
    run: Callable[[GameService, dict[str, JsonValue]], str]
    args: type[BaseModel] = NoArgs


def _next_scene(service: GameService, raw: dict[str, JsonValue]) -> str:
    asked = NextScene.model_validate(raw)
    return service.begin_next_scene(asked.intent, asked.include)


SERVER_TOOLS: tuple[ServerTool, ...] = (
    ServerTool(
        "start_turn",
        "Open the turn and get the whole game back: the scene, who is here, what is hidden here,"
        " the threads, the notes from the rules and the recent play. Call it first every turn.",
        lambda service, _raw: service.start_turn(),
    ),
    ServerTool(
        "scene",
        "The same picture start_turn gives, for when you were compacted mid-turn.",
        lambda service, _raw: service.picture(),
    ),
    ServerTool(
        "next_scene",
        "Brief the worldsmith on what comes next. It returns at once and does not end the turn;"
        " the scene it writes arrives on a later turn.",
        _next_scene,
        NextScene,
    ),
)

DISPATCH = {tool.name: tool for tool in SERVER_TOOLS}


def refusal(turn: Turn, name: str) -> str | None:
    """The legality table: a call that does not fit the moment says what to do instead."""
    if name == "scene":
        return None
    if name == "start_turn":
        return ALREADY_OPEN if turn.started else None
    if not turn.started:
        return START_FIRST
    if (ended := turn.engine.over(turn.draft)) is not None:
        return f"{ended} The game is over; the player restarts from the page."
    # `next_scene` never reaches `Turn.call`, so the pending row is enforced for it here.
    if name == "next_scene" and turn.draft.pending is not None:
        return DECIDING
    return None


def offered(runtime: Runtime) -> list[types.Tool]:
    engine_tools = runtime.engine.tools
    # `call` reaches the server's own tools first, so a shared name would shadow the engine's.
    require_unique("published tool names", (*DISPATCH, *(one.name for one in engine_tools)))
    return [_published(one) for one in (*SERVER_TOOLS, *engine_tools)]


def call(runtime: Runtime, name: str, raw: dict[str, JsonValue]) -> str:
    service = runtime.playing()
    if service is None:
        raise ValueError(NO_TURN)
    turn = service.turn
    if turn is None:
        raise ValueError(NO_TURN)
    if (refused := refusal(turn, name)) is not None:
        raise ValueError(refused)
    tool = DISPATCH.get(name)
    if tool is None:
        return turn.call(name, raw)
    # A NoArgs tool ignores `raw` in its handler, so junk arguments need a guard of their own.
    _ = tool.args.model_validate(raw)
    return tool.run(service, raw)


def _published(tool: ServerTool | DirectorTool) -> types.Tool:
    return types.Tool(
        name=tool.name, description=tool.description, input_schema=schema_of(tool.args)
    )


def build_server(runtime: Runtime) -> Server[dict[str, object]]:
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


def _content(body: str, error: bool = False) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(text=body)], is_error=error)


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


def endpoint(runtime: Runtime) -> Endpoint:
    manager = StreamableHTTPSessionManager(
        app=build_server(runtime),
        json_response=True,
        stateless=True,
        security_settings=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["127.0.0.1:*", "localhost:*"],
            allowed_origins=["http://127.0.0.1:*", "http://localhost:*"],
        ),
    )
    return Endpoint(asgi=StreamableHTTPASGIApp(manager), running=AsyncExitStack(), manager=manager)
