import asyncio
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import mcp_types as types
from mcp.server import NotificationOptions, Server, ServerRequestContext
from mcp.server.stdio import stdio_server
from pydantic import BaseModel, JsonValue, TypeAdapter
from pydantic_ai import ModelRetry
from pydantic_ai.toolsets import ToolsetTool

from aidm.app.runtime import Runtime
from aidm.authoring.draft import WHOLE_SCENARIO, ScenarioDraft
from aidm.authoring.run import authoring_toolset, draft_context
from aidm.config import load_settings
from aidm.engines.core import DirectorTool, NoArgs
from aidm.harness.codemode import BeginScenario, Harness, OpenGame, PlayerActionCall, catalogue
from aidm.llm import schema_of
from aidm.state.play import Answer, Narration

SERVER_NAME = "aidm"

# What the library's own default lifespan yields; this server keeps no state in it.
type LifespanContext = dict[str, Any]

_ARGUMENTS = TypeAdapter(dict[str, JsonValue])


type Handler = Callable[[Harness, dict[str, JsonValue]], str]


@dataclass(frozen=True, slots=True)
class ServerTool:
    """Name, description, behaviour and schema in one place: what is published is what is run."""

    name: str
    description: str
    run: Handler
    args: type[BaseModel] = NoArgs


def _published(tool: ServerTool | DirectorTool) -> types.Tool:
    return types.Tool(
        name=tool.name, description=tool.description, input_schema=schema_of(tool.args)
    )


SERVER_TOOLS: tuple[ServerTool, ...] = (
    ServerTool(
        "list_games",
        "The saves to resume and the scenarios, characters and engines a new game is built from.",
        lambda harness, _raw: catalogue(harness.settings),
    ),
    ServerTool(
        "open_game",
        "Open or resume one game. Nothing else runs until this succeeds.",
        lambda harness, raw: harness.open_game(OpenGame.model_validate(raw).slug),
        OpenGame,
    ),
    ServerTool(
        "rules",
        "How to run a turn here: the director rules, this engine's rules, the narration rules.",
        lambda harness, _raw: harness.rules(),
    ),
    ServerTool(
        "start_turn",
        "Open a turn with the player's action and get the whole game back: canon, canon the player"
        " has not found, threads, rules notes, recent play. Call it first every turn.",
        lambda harness, raw: harness.start_turn(Answer.model_validate(raw)),
        Answer,
    ),
    ServerTool(
        "scene",
        "The same picture start_turn gives, for when you were compacted mid-turn.",
        lambda harness, _raw: harness.scene(),
    ),
    ServerTool(
        "end_turn",
        "Close the turn with the prose the player reads.",
        lambda harness, raw: harness.end_turn(Narration.model_validate(raw)),
        Narration,
    ),
    ServerTool(
        "player_action",
        "Apply one player action the player chose, between turns. Not a Director tool.",
        lambda harness, raw: harness.player_action(PlayerActionCall.model_validate(raw)),
        PlayerActionCall,
    ),
    ServerTool(
        "begin_growth",
        "Open an authoring run that writes new unknown canon into the open game's world.",
        lambda harness, _raw: harness.begin_growth(),
    ),
    ServerTool(
        "begin_scenario",
        "Open an authoring run that writes a whole new scenario. No game need be open.",
        lambda harness, raw: harness.begin_scenario(BeginScenario.model_validate(raw)),
        BeginScenario,
    ),
    ServerTool(
        "finish_growth",
        "Check the grown draft and materialize it into the open game as canon to be found.",
        lambda harness, _raw: harness.finish_growth(),
    ),
    ServerTool(
        "finish_scenario",
        "Check the draft and write it to disk as a scenario anyone can play.",
        lambda harness, _raw: harness.finish_scenario(),
    ),
)

DISPATCH = {tool.name: tool for tool in SERVER_TOOLS}
PUBLISHED = tuple(_published(tool) for tool in SERVER_TOOLS)

# Names and schemas only: a call routes to the open run's own toolset, which has an engine to play.
AUTHORING = authoring_toolset(None, WHOLE_SCENARIO)
AUTHORING_TOOLS = frozenset(AUTHORING.tools)


def _as_mcp_tool[D](tool: ToolsetTool[D]) -> types.Tool:
    definition = tool.tool_def
    return types.Tool(
        name=definition.name,
        description=definition.description or "",
        input_schema=definition.parameters_json_schema,
    )


async def _authoring_tools() -> list[types.Tool]:
    """Listed off an empty draft: their schemas never vary, so a driver sees them from the start."""
    tools = await AUTHORING.get_tools(draft_context(ScenarioDraft()))
    return [_as_mcp_tool(tool) for tool in tools.values()]


async def offered(harness: Harness) -> list[types.Tool]:
    tools = [*PUBLISHED, *await _authoring_tools()]
    if harness.session is None:
        return tools
    tools.extend(_published(one) for one in harness.session.engine.director_tools)
    return tools


async def call(harness: Harness, name: str, raw: dict[str, JsonValue]) -> str:
    tool = DISPATCH.get(name)
    if tool is not None:
        # A NoArgs tool ignores `raw` in its handler, so junk arguments need a guard of their own.
        _ = tool.args.model_validate(raw)
        return tool.run(harness, raw)
    if name in AUTHORING_TOOLS:
        return await harness.authoring_tool(name, raw)
    return harness.call_director_tool(name, raw)


def build_server(harness: Harness) -> Server[LifespanContext]:
    async def on_list_tools(
        ctx: ServerRequestContext[LifespanContext], params: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        del ctx, params
        async with harness.lock:
            return types.ListToolsResult(tools=await offered(harness))

    async def on_call_tool(
        ctx: ServerRequestContext[LifespanContext], params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        """The lock replaces the builtin loop's sequential toolset: Claude Code parallelises."""
        async with harness.lock:
            try:
                answered = await call(
                    harness, params.name, _ARGUMENTS.validate_python(params.arguments or {})
                )
            except (ModelRetry, ValueError) as refused:
                return _content(str(refused), error=True)
        if params.name == "open_game":
            await ctx.session.send_tool_list_changed()
        return _content(answered)

    return Server(SERVER_NAME, on_list_tools=on_list_tools, on_call_tool=on_call_tool)


def _content(body: str, error: bool = False) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(text=body)], is_error=error)


async def serve(harness: Harness) -> None:
    server = build_server(harness)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(NotificationOptions(tools_changed=True)),
        )


def main() -> None:
    # stdout is the MCP transport, so every log line has to go to stderr.
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    settings = load_settings()
    # Read from .env, not a flag, so a viewer beside this server can never be a second writer.
    # Any code-mode value: `codex` strips the environment of the CLIs it spawns, so a driver
    # cannot hand its child a value here.
    if not settings.code_mode:
        raise SystemExit("set HARNESS to a code-mode value in .env before running this server")
    asyncio.run(serve(Harness(settings=settings, runtime=Runtime(settings))))


if __name__ == "__main__":
    main()
