import asyncio
import json
import logging
from dataclasses import dataclass, field
from functools import cached_property, partial
from pathlib import Path

from pydantic import ConfigDict, Field, JsonValue
from pydantic_ai import ModelRetry
from pydantic_ai.toolsets import FunctionToolset

from aidm.app.launch import (
    LauncherCatalog,
    LauncherController,
    LaunchTarget,
    load_catalog,
)
from aidm.app.runtime import GameSession, Runtime
from aidm.authoring.draft import ScenarioDraft, playtest_check
from aidm.authoring.run import (
    AuthoringRun,
    GrowthRun,
    ScenarioRun,
    authoring_toolset,
    briefing,
    draft_context,
    growth_run,
    scenario_run,
)
from aidm.config import Settings
from aidm.state.entities import EngineId, Frozen, Slug
from aidm.state.facts import traced
from aidm.state.model import Game
from aidm.state.play import (
    Answer,
    Narration,
    PendingDecision,
)
from aidm.turn.context import (
    NARRATOR,
    SceneSnapshot,
    director_instructions,
    player_scene,
    render_director,
)
from aidm.turn.run import Turn, speakers_refusal

LOGGER = logging.getLogger(__name__)

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
    """An existing save's slug, or `<scenario>--<character>` to begin a new game."""


class BeginScenario(ToolArgs):
    slug: Slug
    """Directory name for the new scenario: lowercase words joined by hyphens."""
    premise: str
    """What the scenario is about, in a few sentences. Empty when `source` carries it."""
    engine: EngineId
    """Rules engine the finished scenario must be playable under."""
    grows: bool = False
    """Whether the world keeps writing itself in play. Then this run writes only the opening."""
    packs: tuple[Slug, ...] = ("srd",)
    """Selected pack ids, always including srd."""
    source: str = ""
    """Path to a .md, .txt or .pdf adventure to author from. Empty to author from the premise."""


class PlayerActionCall(Frozen):
    name: Slug = Field(description="Exact name from YOU CAN.")
    args: dict[str, JsonValue] = Field(default_factory=dict, description="Exact args from YOU CAN.")


@dataclass
class Harness:
    """One game, one lock, one turn in flight."""

    settings: Settings
    runtime: Runtime
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    session: GameSession | None = None
    turn: Turn | None = None
    authoring: AuthoringRun | None = None

    @cached_property
    def blank_authoring(self) -> FunctionToolset[ScenarioDraft]:
        """Names and schemas only: the SDK lists tools once at connect, before any run is open."""
        return authoring_toolset(
            playtest_check(self.settings, next(iter(self.runtime.engines.values())))
        )

    def opened(self) -> GameSession:
        if self.session is None:
            raise ModelRetry(
                f"no game is open; call open_game(slug) first.\n{catalogue(self.runtime)}"
            )
        return self.session

    def started(self) -> Turn:
        if self.turn is None:
            raise ModelRetry("no turn is open; call start_turn with the player's message first.")
        return self.turn

    def open_game(self, slug: str) -> str:
        target = _target(load_catalog(self.settings, self.runtime.engines), slug)
        session = self.runtime.session(target)
        self.session = session
        self.turn = None
        # A growth run drafts against the game it began in; opening another abandons it.
        if isinstance(self.authoring, GrowthRun):
            self.authoring = None
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
        return f"{PREAMBLE}\n{director_instructions(engine.director_instructions)}\n\n{NARRATOR}"

    def scene(self) -> str:
        return self._picture()

    def _picture(self) -> str:
        session = self.opened()
        state = session.state
        recent = self.settings.turn.recent_exchanges
        turn = self.turn
        rendered = (
            turn.picture()
            if turn is not None
            else render_director(
                SceneSnapshot.from_game(state, session.engine.notes(state)),
                partial(session.engine.describe, state),
                state.scenario,
                NO_TURN_OPEN,
            )
        )
        sections = [
            f"RECENT PLAY (this is turn {state.turn + 1}):\n{_recent(state, recent)}",
            rendered,
            f"WAITING ON THE PLAYER:\n{_waiting(state.pending)}",
        ]
        if listing := _offers_listing(session):
            sections.append(f"YOU CAN:\n{listing}")
        # A compacted session that missed the `end_turn` note still reads it here.
        if session.growth_due():
            sections.append(GROWTH_DUE)
        return "\n\n".join(sections)

    def start_turn(self, answer: Answer) -> str:
        session = self.opened()
        self.turn = Turn.begin(
            session.engine,
            session.state,
            answer,
            session.rng,
            lambda draft: session.commit(draft.committed()),
        )
        return self._picture()

    def end_turn(self, closing: Narration) -> str:
        session = self.opened()
        turn = self.started()
        lines = closing.lines
        if not lines and turn.draft.pending is None:
            raise ModelRetry(
                "write the narration lines: a turn with neither prose nor an open "
                "decision shows the player nothing."
            )
        if refused := speakers_refusal(player_scene(turn.draft), lines):
            raise ModelRetry(refused)
        state, trace = turn.finish(lines)
        session.commit(state, trace)
        self.turn = None
        closed = f"turn {state.turn} committed."
        return f"{closed}\n{GROWTH_DUE}" if session.growth_due() else closed

    def call_director_tool(self, name: str, raw: dict[str, JsonValue]) -> str:
        return self.started().call(name, raw)

    def player_action(self, call: PlayerActionCall) -> str:
        session = self.opened()
        if self.turn is not None:
            raise ModelRetry("a turn is open; the player acts for themself only between turns.")
        try:
            facts = session.act(call.name, call.args)
        except ValueError as refused:
            raise ModelRetry(f"{refused}\n{_offers_listing(session)}") from refused
        return traced(facts)

    def begin_growth(self) -> str:
        session = self.opened()
        if not session.scenario.grows:
            raise ModelRetry(f"{session.slug!r} does not write itself; there is nothing to grow.")
        # Refusing an un-due begin keeps the world from growing on a whim.
        if not session.growth_due():
            raise ModelRetry("the player still has places to find; grow the world when it is due.")
        run = growth_run(session.settings, session.engine, session.character, session.state)
        self._hold(run)
        return briefing(run, "finish_growth")

    def begin_scenario(self, asked: BeginScenario) -> str:
        engine = self.runtime.engines.get(asked.engine)
        if engine is None:
            raise ModelRetry(f"unknown engine {asked.engine!r}")
        run = scenario_run(
            self.settings,
            engine,
            asked.slug,
            asked.premise,
            asked.grows,
            Path(asked.source) if asked.source else None,
            packs=asked.packs,
        )
        self._hold(run)
        return briefing(run, "finish_scenario")

    async def authoring_tool(self, name: str, raw: dict[str, JsonValue]) -> str:
        run = self.authoring
        if run is None:
            raise ModelRetry("no authoring run is open; call begin_growth or begin_scenario.")
        ctx = draft_context(run.draft, name)
        tool = (await run.toolset.get_tools(ctx))[name]
        answered = await run.toolset.call_tool(
            name, tool.args_validator.validate_python(raw), ctx, tool
        )
        return str(answered)

    def finish_growth(self) -> str:
        session = self.opened()
        run = self.authoring
        if not isinstance(run, GrowthRun):
            raise ModelRetry("no growth run is open; call begin_growth first.")
        _check_playable(run)
        landed = session.apply_growth(run.patch())
        self.authoring = None
        return traced(landed)

    def finish_scenario(self) -> str:
        run = self.authoring
        if not isinstance(run, ScenarioRun):
            raise ModelRetry("no scenario run is open; call begin_scenario first.")
        _check_playable(run)
        written = run.write()
        self.authoring = None
        return written

    def _hold(self, run: AuthoringRun) -> None:
        """Beginning replaces: a driver that died mid-draft left nothing durable behind."""
        if self.authoring is not None:
            LOGGER.info("discarding the authoring run still open")
        self.authoring = run


def _check_playable(run: AuthoringRun) -> None:
    if reason := run.refusal():
        raise ModelRetry(f"the draft does not play yet, so it is not finished: {reason}")


def _target(catalog: LauncherCatalog, slug: str) -> LaunchTarget:
    controller = LauncherController(catalog)
    if any(save.slug == slug for save in catalog.saves):
        return controller.resume(slug)
    named = slug.split("--")
    if len(named) != 2:
        raise ModelRetry(
            f"{slug!r} is neither a save nor <scenario>--<character>.\n{_listing(catalog)}"
        )
    scenario_id, character_id = named
    try:
        controller.choose_scenario(scenario_id)
        controller.choose_character(character_id)
    except ValueError as unknown:
        raise ModelRetry(f"{unknown}\n{_listing(catalog)}") from unknown
    return controller.new_game()


def catalogue(runtime: Runtime) -> str:
    return _listing(load_catalog(runtime.settings, runtime.engines))


def _listing(catalog: LauncherCatalog) -> str:
    return "\n".join(
        (
            "saves: " + (", ".join(save.slug for save in catalog.saves) or "(none)"),
            "scenarios: " + ", ".join(entry.id for entry in catalog.scenarios),
            "characters: " + ", ".join(entry.id for entry in catalog.characters),
            "engines: " + ", ".join(option.id for option in catalog.engines),
        )
    )


def _recent(state: Game, limit: int) -> str:
    told = [
        f"> {exchange.prompt}\n[at {exchange.place}] {exchange.narration}"
        for exchange in state.history[-limit:]
    ]
    return "\n\n".join(told) or "(the game has not started yet)"


def _waiting(pending: PendingDecision | None) -> str:
    if pending is None:
        return "- (nothing; the turn is yours to run)"
    lines = [f"- {one.id}: {one.label} {one.detail}".rstrip() for one in pending.options]
    lines.append(
        "- (the player answers in their own words)"
        if pending.allows_text
        else "- (choose one option above)"
    )
    return "\n".join([f"{pending.kind}: {pending.prompt}", *lines])


def _offers_listing(session: GameSession) -> str:
    return "\n".join(
        f"- {offer.label}: player_action(name={action.name}, args={json.dumps(offer.args)})"
        for action, offer in session.offers()
    )
