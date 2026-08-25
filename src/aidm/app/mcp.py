import asyncio
import logging
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import mcp_types as types
from mcp.server import NotificationOptions, Server, ServerRequestContext
from mcp.server.stdio import stdio_server
from pydantic import ConfigDict, Field, JsonValue, TypeAdapter, create_model
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool
from pydantic_ai.usage import RunUsage

from aidm.app.authoring import (
    WHOLE_SCENARIO,
    AuthoringRun,
    GrowthRun,
    ScenarioDraft,
    ScenarioRun,
    authoring_toolset,
    briefing,
    growth_run,
    scenario_run,
)
from aidm.app.launch import (
    LauncherCatalog,
    LauncherController,
    LaunchTarget,
    as_engine_id,
    load_catalog,
)
from aidm.app.runtime import DraftedAdvance, GameSession, Runtime
from aidm.config import Settings, load_settings
from aidm.engines.core import Advancement, DirectorContext, ProposalBase, TurnRecord
from aidm.state.entities import EngineId, EntityId, Frozen, Slug
from aidm.state.facts import Fact
from aidm.state.model import Game
from aidm.state.play import (
    Answer,
    Line,
    OptionId,
    PendingDecision,
    TurnTrace,
    narration_text,
)
from aidm.turn.context import (
    NARRATOR,
    SceneSnapshot,
    advisor_instructions,
    director_instructions,
    player_scene,
    render_director,
)
from aidm.turn.run import close_segment, consume_answer, gated_toolsets, speakers_refusal

LOGGER = logging.getLogger(__name__)

# What the library's own default lifespan yields; this server keeps no state in it.
type LifespanContext = dict[str, Any]

SERVER_NAME = "aidm"
RECENT_EXCHANGES = 8
# Where `uv run aidm` serves the viewer; the port is NiceGUI's default, set in ui/app.py.
VIEWER = "http://localhost:8080"
# `render_director` labels its last section PLAYER ACTION; before `start_turn` there is none.
NO_TURN_OPEN = "(no turn is open; call start_turn with the player's message)"

PREAMBLE = """\
CODE MODE. You are the Director and the Narrator of this game at once. The two rule sets below
were written for two separate models. Here you play both. The Director rules say that a Narrator
after you writes the prose. Ignore that line. You write the prose yourself, and you give it to
`end_turn`.

The player's action reaches you as a chat message, never as a tool argument. Call
`start_turn(the player's message)` first every turn: it opens the turn and hands back the whole
picture of the game. Then call director tools one at a time, and read each result before the next
call. Then call `end_turn` with the lines you wrote. If you were compacted mid-turn, `scene()`
gives the picture back.

`scene()` shows you canon the player has not discovered. Never put undiscovered canon in a
narration line. Reveal it with a tool first, or leave it out.
"""

GROWTH_DUE = """\
WORLD GROWTH DUE: this scenario writes itself, and the player is nearly out of places to find.
Grow the world before the next turn. Spawn a subagent and tell it to run the growing-aidm skill.
Run that skill here only if you cannot spawn a subagent."""


class ToolArgs(Frozen):
    # Without this the field docstrings below never reach the schema the model reads.
    model_config = ConfigDict(use_attribute_docstrings=True)


class OpenGame(ToolArgs):
    slug: str
    """An existing save's slug, or `<scenario>--<character>--<engine>` to begin a new game."""


class NoArgs(ToolArgs):
    pass


class StartTurn(ToolArgs):
    prompt: str
    """What the player did, in their words."""
    option_id: OptionId | None = None
    """Exact id of the listed option their words chose, when a decision is open."""


class EndTurn(ToolArgs):
    lines: tuple[Line, ...]
    """The prose the player reads, in order."""


class AdvanceArgs(ToolArgs):
    """`proposal` is replaced by the engine's own proposal type before the model ever sees it."""

    subject_id: EntityId
    """Exact id of the character the offer names."""
    proposal: ProposalBase


class BeginScenario(ToolArgs):
    slug: Slug
    """Directory name for the new scenario: lowercase words joined by hyphens."""
    premise: str
    """What the scenario is about, in a few sentences. Empty when `source` carries it."""
    engines: tuple[EngineId, ...]
    """Rules engines the finished scenario must be playable under."""
    grows: bool = False
    """Whether the world keeps writing itself in play. Then this run writes only the opening."""
    source: str = ""
    """Path to a .md, .txt or .pdf adventure to author from. Empty to author from the premise."""


class Summary(ToolArgs):
    summary: str
    """Two or three sentences on what this run wrote."""


_ARGUMENTS = TypeAdapter(dict[str, JsonValue])


@dataclass
class Turn:
    """Turn-scoped state the per-call commits must not lose."""

    prompt: str
    notes: tuple[str, ...] = ()
    log: TurnRecord = field(default_factory=TurnRecord)
    answered: PendingDecision | None = None
    # The answer re-suspended: core tools may still develop what it caused.
    suspended_at_start: bool = False


@dataclass
class Harness:
    """The composition root of code mode: one game, one lock, one turn in flight."""

    settings: Settings
    runtime: Runtime
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    session: GameSession | None = None
    toolsets: tuple[AbstractToolset[DirectorContext], ...] = ()
    turn: Turn | None = None
    advance_args: type[AdvanceArgs] | None = None
    authoring: AuthoringRun | None = None

    def opened(self) -> GameSession:
        if self.session is None:
            raise ModelRetry(
                f"no game is open; call open_game(slug) first.\n{_catalogue(self.settings)}"
            )
        return self.session

    def started(self) -> Turn:
        if self.turn is None:
            raise ModelRetry("no turn is open; call start_turn with the player's message first.")
        return self.turn

    async def offered(self) -> list[types.Tool]:
        offered = [*PUBLISHED, *await _authoring_tools()]
        if self.session is None:
            return offered
        if self.advance_args is not None:
            offered.extend(_advance_tools(self.advance_args))
        _, tools = await self._director_tools(None)
        offered.extend(_as_mcp_tool(tool) for tool in tools.values())
        return offered

    async def call(self, name: str, raw: dict[str, JsonValue]) -> str:
        tool = DISPATCH.get(name)
        if tool is not None:
            return tool.run(self, raw)
        if name in AUTHORING_TOOLS:
            return await self.authoring_tool(name, raw)
        return await self.call_director_tool(name, raw)

    def open_game(self, slug: str) -> str:
        target = _target(load_catalog(self.settings), slug)
        session = self.runtime.session(target)
        self.session = session
        self.toolsets = tuple(gated_toolsets(session.engine))
        self.turn = None
        # A growth run drafts against the game it began in; opening another abandons it.
        if isinstance(self.authoring, GrowthRun):
            self.authoring = None
        advancement = session.engine.advancement
        self.advance_args = None if advancement is None else _advance_args(advancement)
        # A new game lives only in memory until something commits, and the viewer reads the file.
        if session.store.stamp(session.slug) == 0:
            session.commit(session.state)
        return (
            f"opened {target.slug!r} at turn {session.state.turn}, "
            f"playing {target.scenario_id} under the {session.engine.id} engine. "
            "Call rules(), then start_turn with the player's message.\n"
            f"Show the player this link once: {VIEWER}{target.path} — a window that follows "
            "the game while `uv run aidm` runs in another terminal."
        )

    def rules(self) -> str:
        engine = self.opened().engine
        rules = f"{PREAMBLE}\n{director_instructions(engine.director_instructions)}\n\n{NARRATOR}"
        if engine.advancement is None:
            return rules
        return f"{rules}\n\n{advisor_instructions(engine.advancement.instructions)}"

    def scene(self) -> str:
        turn = self.turn
        return self._picture(
            NO_TURN_OPEN if turn is None else turn.prompt, () if turn is None else turn.notes
        )

    def _picture(self, action: str, notes: tuple[str, ...], resumed: str = "") -> str:
        session = self.opened()
        state = session.state
        rendered = render_director(
            SceneSnapshot.from_game(state, (*notes, *state.world.pending_notes)),
            session.engine.renderer(state),
            state.scenario,
            action,
            resumed=resumed,
        )
        sections = [
            rendered,
            f"RECENT PLAY (this is turn {state.turn + 1}):\n{_recent(state)}",
            f"WAITING ON THE PLAYER:\n{_waiting(state.pending)}",
            f"ADVANCEMENT ON OFFER:\n{_offers(session)}",
        ]
        # A compacted session that missed the `end_turn` note still reads it here.
        if session.growth_due():
            sections.append(GROWTH_DUE)
        return "\n\n".join(sections)

    def start_turn(self, asked: StartTurn) -> str:
        session = self.opened()
        draft = session.state.draft()
        log = TurnRecord()
        chose = asked.option_id
        answer = Answer(option_id=chose) if chose is not None else Answer(text=asked.prompt)
        prompt, resumed, answered = consume_answer(session.engine, draft, answer, session.rng, log)
        notes = draft.take_notes()
        session.commit(draft.committed())
        self.turn = Turn(
            prompt=prompt,
            notes=notes,
            log=log,
            answered=answered,
            suspended_at_start=draft.pending is not None,
        )
        return self._picture(prompt, notes, resumed=resumed)

    def end_turn(self, closing: EndTurn) -> str:
        session = self.opened()
        turn = self.started()
        lines = closing.lines
        draft = session.state.draft()
        if not lines and draft.pending is None:
            raise ModelRetry(
                "write the narration lines: a turn with neither prose nor an open "
                "decision shows the player nothing."
            )
        if refused := speakers_refusal(player_scene(draft), lines):
            raise ModelRetry(refused)
        state = close_segment(draft, turn.prompt, tuple(lines), tuple(turn.log.events))
        session.commit(
            state,
            TurnTrace(
                prompt=turn.prompt,
                facts=tuple(turn.log.facts),
                narration=narration_text(lines),
            ),
        )
        self.turn = None
        closed = f"turn {state.turn} committed."
        return f"{closed}\n{GROWTH_DUE}" if session.growth_due() else closed

    async def call_director_tool(self, name: str, raw: dict[str, JsonValue]) -> str:
        session = self.opened()
        _ = self.started()
        ctx, tools = await self._director_tools(name)
        tool = tools.get(name)
        if tool is None:
            raise ModelRetry(_unavailable(name, session.state.pending))
        answered = await tool.toolset.call_tool(
            name, tool.args_validator.validate_python(raw), ctx, tool
        )
        session.commit(ctx.deps.draft.committed())
        return str(answered)

    def propose_advance(self, raw: dict[str, JsonValue]) -> str:
        session = self.opened()
        advancement = session.engine.advancement
        if advancement is None or self.advance_args is None:
            raise ModelRetry(f"the {session.engine.id!r} engine has no advancement.")
        asked = self.advance_args.model_validate(raw)
        offer = next((one for one in session.offers() if one.subject_id == asked.subject_id), None)
        if offer is None:
            raise ModelRetry(f"nothing is on offer for {asked.subject_id!r}.")
        # The same refusal the builtin advisor retries against, run here against live state.
        if refused := advancement.advance_refusal(session.state, offer, asked.proposal):
            raise ModelRetry(refused)
        drafted = DraftedAdvance(offer=offer, proposal=asked.proposal)
        session.drafted = drafted
        return (
            f"proposed for {asked.subject_id}:\n{_traces(session.preview(drafted))}\n"
            "Show the player, then call apply_advance() if they accept."
        )

    def apply_advance(self) -> str:
        session = self.opened()
        drafted = session.drafted
        if drafted is None:
            raise ModelRetry("nothing is drafted; call propose_advance first.")
        landed = session.apply_proposal(drafted)
        session.drafted = None
        return _traces(landed)

    def begin_growth(self) -> str:
        session = self.opened()
        if not session.scenario.grows:
            raise ModelRetry(f"{session.slug!r} does not write itself; there is nothing to grow.")
        # Refusing an un-due begin keeps the world from growing on a whim.
        if not session.growth_due():
            raise ModelRetry("the player still has places to find; grow the world when it is due.")
        run = growth_run(session.settings, session.engine, session.character, session.state)
        self._hold(run)
        return briefing(session.settings, run.brief, run.opening_prompt, "finish_growth")

    def begin_scenario(self, asked: BeginScenario) -> str:
        run = scenario_run(
            self.settings,
            asked.slug,
            asked.premise,
            asked.grows,
            asked.engines,
            Path(asked.source) if asked.source else None,
        )
        self._hold(run)
        return briefing(self.settings, run.brief, run.opening_prompt, "finish_scenario")

    async def authoring_tool(self, name: str, raw: dict[str, JsonValue]) -> str:
        run = self.authoring
        if run is None:
            raise ModelRetry("no authoring run is open; call begin_growth or begin_scenario.")
        ctx = _authoring_context(run.draft, name)
        tool = (await run.toolset.get_tools(ctx))[name]
        answered = await run.toolset.call_tool(
            name, tool.args_validator.validate_python(raw), ctx, tool
        )
        return str(answered)

    def finish_growth(self, summary: str) -> str:
        session = self.opened()
        run = self.authoring
        if not isinstance(run, GrowthRun):
            raise ModelRetry("no growth run is open; call begin_growth first.")
        _check_playable(run)
        landed = session.apply_growth(run.patch())
        self.authoring = None
        return f"{summary}\n{_traces(landed)}"

    def finish_scenario(self, summary: str) -> str:
        run = self.authoring
        if not isinstance(run, ScenarioRun):
            raise ModelRetry("no scenario run is open; call begin_scenario first.")
        _check_playable(run)
        written = run.write()
        self.authoring = None
        return f"{summary}\n{written}"

    def _hold(self, run: AuthoringRun) -> None:
        """Beginning replaces: a driver that died mid-draft left nothing durable behind."""
        if self.authoring is not None:
            LOGGER.info("discarding the authoring run still open")
        self.authoring = run

    async def _director_tools(
        self, tool_name: str | None
    ) -> tuple[RunContext[DirectorContext], dict[str, ToolsetTool[DirectorContext]]]:
        """A fresh draft per call: an accepted call commits, so no draft outlives its tool."""
        session = self.opened()
        # Listing what is offered reads committed state, so it needs no open turn.
        turn = self.turn or Turn(prompt="")
        ctx = RunContext(
            deps=DirectorContext(
                engine=session.engine,
                draft=session.state.draft(),
                rng=session.rng,
                log=turn.log,
                suspended_at_start=turn.suspended_at_start,
                answered=turn.answered,
            ),
            # A RunContext needs a model; no director tool reads one.
            model=TestModel(),
            usage=RunUsage(),
            tool_name=tool_name,
        )
        tools: dict[str, ToolsetTool[DirectorContext]] = {}
        for toolset in self.toolsets:
            tools |= await toolset.get_tools(ctx)
        return ctx, tools


type Handler = Callable[[Harness, dict[str, JsonValue]], str]


@dataclass(frozen=True, slots=True)
class ServerTool:
    """Name, description, behaviour and schema in one place: what is published is what is run."""

    name: str
    description: str
    run: Handler
    args: type[ToolArgs] = NoArgs
    # False when the call cannot change which tools are offered, so no list_changed follows it.
    reshapes: bool = True

    def published(self) -> types.Tool:
        return types.Tool(
            name=self.name,
            description=self.description,
            input_schema=self.args.model_json_schema(),
        )


SERVER_TOOLS: tuple[ServerTool, ...] = (
    ServerTool(
        "list_games",
        "The saves to resume and the scenarios, characters and engines a new game is built from.",
        lambda harness, _raw: _catalogue(harness.settings),
        reshapes=False,
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
        reshapes=False,
    ),
    ServerTool(
        "start_turn",
        "Open a turn with the player's action and get the whole game back: canon, canon the player"
        " has not found, threads, rules notes, recent play. Call it first every turn.",
        lambda harness, raw: harness.start_turn(StartTurn.model_validate(raw)),
        StartTurn,
    ),
    ServerTool(
        "scene",
        "The same picture start_turn gives, for when you were compacted mid-turn.",
        lambda harness, _raw: harness.scene(),
        reshapes=False,
    ),
    ServerTool(
        "end_turn",
        "Close the turn with the prose the player reads.",
        lambda harness, raw: harness.end_turn(EndTurn.model_validate(raw)),
        EndTurn,
    ),
    ServerTool(
        "begin_growth",
        "Open an authoring run that writes new unknown canon into the open game's world.",
        lambda harness, _raw: harness.begin_growth(),
        reshapes=False,
    ),
    ServerTool(
        "begin_scenario",
        "Open an authoring run that writes a whole new scenario. No game need be open.",
        lambda harness, raw: harness.begin_scenario(BeginScenario.model_validate(raw)),
        BeginScenario,
        reshapes=False,
    ),
    ServerTool(
        "finish_growth",
        "Check the grown draft and materialize it into the open game as canon to be found.",
        lambda harness, raw: harness.finish_growth(Summary.model_validate(raw).summary),
        Summary,
    ),
    ServerTool(
        "finish_scenario",
        "Check the draft and write it to disk as a scenario anyone can play.",
        lambda harness, raw: harness.finish_scenario(Summary.model_validate(raw).summary),
        Summary,
        reshapes=False,
    ),
)

# Published only while the open engine has advancement, so they sit outside SERVER_TOOLS.
PROPOSE_ADVANCE = ServerTool(
    "propose_advance",
    "Draft one advancement the player asked for; nothing commits until `apply_advance`.",
    lambda harness, raw: harness.propose_advance(raw),
    AdvanceArgs,
)
APPLY_ADVANCE = ServerTool(
    "apply_advance",
    "Commit the drafted advancement.",
    lambda harness, _raw: harness.apply_advance(),
)

DISPATCH = {tool.name: tool for tool in (*SERVER_TOOLS, PROPOSE_ADVANCE, APPLY_ADVANCE)}
PUBLISHED = tuple(tool.published() for tool in SERVER_TOOLS)

# One instance: its tools are listed from here and called against whichever draft is open.
AUTHORING = authoring_toolset((), WHOLE_SCENARIO)
AUTHORING_TOOLS = frozenset(AUTHORING.tools)


def reshapes(name: str) -> bool:
    """A director tool commits game state and re-gates the list; an authoring tool cannot."""
    tool = DISPATCH.get(name)
    return tool.reshapes if tool is not None else name not in AUTHORING_TOOLS


def _unavailable(name: str, pending: PendingDecision | None) -> str:
    if pending is None:
        return f"{name!r} does not apply in this state; call scene() and use what fits."
    return (
        f"the rules are waiting on the player: {pending.prompt}\n"
        "Put that to the player, then call start_turn with their answer."
    )


def _as_mcp_tool[D](tool: ToolsetTool[D]) -> types.Tool:
    definition = tool.tool_def
    return types.Tool(
        name=definition.name,
        description=definition.description or "",
        input_schema=definition.parameters_json_schema,
    )


def _advance_args(advancement: Advancement) -> type[AdvanceArgs]:
    """The proposal the model writes is the engine's own type, so the schema it reads is too."""
    return create_model(
        "ProposeAdvance",
        __base__=AdvanceArgs,
        proposal=(
            advancement.proposal_type,
            Field(description="The change to draft, in this engine's own vocabulary."),
        ),
    )


def _advance_tools(args: type[AdvanceArgs]) -> tuple[types.Tool, ...]:
    return (replace(PROPOSE_ADVANCE, args=args).published(), APPLY_ADVANCE.published())


def _authoring_context(
    draft: ScenarioDraft, tool_name: str | None = None
) -> RunContext[ScenarioDraft]:
    # A RunContext needs a model; no authoring tool reads one.
    return RunContext(deps=draft, model=TestModel(), usage=RunUsage(), tool_name=tool_name)


async def _authoring_tools() -> list[types.Tool]:
    """Listed off an empty draft: their schemas never vary, so a driver sees them from the start."""
    tools = await AUTHORING.get_tools(_authoring_context(ScenarioDraft()))
    return [_as_mcp_tool(tool) for tool in tools.values()]


def _check_playable(run: AuthoringRun) -> None:
    if reason := run.refusal():
        raise ModelRetry(f"the draft does not play yet, so it is not finished: {reason}")


def _target(catalog: LauncherCatalog, slug: str) -> LaunchTarget:
    controller = LauncherController(catalog)
    if any(save.slug == slug for save in catalog.saves):
        return controller.resume(slug)
    named = slug.split("--")
    if len(named) != 3:
        raise ModelRetry(
            f"{slug!r} is neither a save nor <scenario>--<character>--<engine>.\n"
            f"{_listing(catalog)}"
        )
    scenario_id, character_id, engine = named
    try:
        controller.choose_scenario(scenario_id)
        controller.choose_engine(as_engine_id(engine))
        controller.choose_character(character_id)
    except ValueError as unknown:
        raise ModelRetry(f"{unknown}\n{_listing(catalog)}") from unknown
    return controller.new_game()


def _catalogue(settings: Settings) -> str:
    return _listing(load_catalog(settings))


def _listing(catalog: LauncherCatalog) -> str:
    return "\n".join(
        (
            "saves: " + (", ".join(save.slug for save in catalog.saves) or "(none)"),
            "scenarios: " + ", ".join(entry.id for entry in catalog.scenarios),
            "characters: " + ", ".join(entry.id for entry in catalog.characters),
            "engines: " + ", ".join(option.id for option in catalog.engines),
        )
    )


def _recent(state: Game) -> str:
    told = [
        f"> {exchange.prompt}\n[at {exchange.place}] {exchange.narration}"
        for exchange in state.history[-RECENT_EXCHANGES:]
    ]
    return "\n\n".join(told) or "(the game has not started yet)"


def _waiting(pending: PendingDecision | None) -> str:
    if pending is None:
        return "- (nothing; the turn is yours to run)"
    options = "\n".join(f"- {one.id}: {one.label} {one.detail}".rstrip() for one in pending.options)
    return f"{pending.prompt}\n{options or '- (the player answers in their own words)'}"


def _offers(session: GameSession) -> str:
    """The offer's rules text rides along: it is what an advance may buy under this engine."""
    listed = [
        f"- {offer.subject_id}: {offer.prompt}" + (f"\n{offer.text}" if offer.text else "")
        for offer in session.offers()
    ]
    return "\n".join(listed) or "- (none)"


def _traces(facts: Sequence[Fact]) -> str:
    return "\n".join(f"- {fact.trace}" for fact in facts) or "- (nothing changed)"


def build_server(harness: Harness) -> Server[LifespanContext]:
    async def on_list_tools(
        ctx: ServerRequestContext[LifespanContext], params: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        del ctx, params
        async with harness.lock:
            return types.ListToolsResult(tools=await harness.offered())

    async def on_call_tool(
        ctx: ServerRequestContext[LifespanContext], params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        """The lock replaces the builtin loop's sequential toolset: Claude Code parallelises."""
        async with harness.lock:
            try:
                answered = await harness.call(
                    params.name, _ARGUMENTS.validate_python(params.arguments or {})
                )
            except (ModelRetry, ValueError) as refused:
                return _content(str(refused), error=True)
        if reshapes(params.name):
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
    if not settings.code_mode:
        raise SystemExit("set HARNESS=code in .env before running the code-mode server")
    asyncio.run(serve(Harness(settings=settings, runtime=Runtime(settings))))


if __name__ == "__main__":
    main()
