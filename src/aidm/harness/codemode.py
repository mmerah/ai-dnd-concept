import asyncio
from dataclasses import dataclass, field

from pydantic import ConfigDict, JsonValue
from pydantic_ai import ModelRetry

from aidm.app.launch import (
    LauncherCatalog,
    LaunchTarget,
    launch_target,
    load_catalog,
)
from aidm.app.runtime import GameService, Runtime
from aidm.config import Settings
from aidm.state.entities import Frozen
from aidm.state.model import Game
from aidm.state.play import (
    Answer,
    Narration,
    PendingDecision,
)
from aidm.turn.context import NARRATOR, director_instructions, render_director
from aidm.turn.run import Turn, speakers_refusal

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


class ToolArgs(Frozen):
    # Without this the field docstrings below never reach the schema the model reads.
    model_config = ConfigDict(use_attribute_docstrings=True)


class OpenGame(ToolArgs):
    slug: str
    """An existing save's slug, or `<scenario>--<character>` to begin a new game."""


@dataclass
class Harness:
    settings: Settings
    runtime: Runtime
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    session: GameService | None = None
    turn: Turn | None = None

    def opened(self) -> GameService:
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
        return f"{PREAMBLE}\n{director_instructions(engine.instructions)}\n\n{NARRATOR}"

    def scene(self) -> str:
        session = self.opened()
        state = session.state
        recent = self.settings.turn.recent_exchanges
        turn = self.turn
        rendered = (
            turn.picture()
            if turn is not None
            else render_director(
                session.view().director.sections,
                state.scenario,
                NO_TURN_OPEN,
                notes=state.notes,
            )
        )
        sections = [
            f"RECENT PLAY (this is turn {state.turn + 1}):\n{_recent(state, recent)}",
            rendered,
            f"WAITING ON THE PLAYER:\n{_waiting(state.pending)}",
        ]
        return "\n\n".join(sections)

    def start_turn(self, answer: Answer) -> str:
        session = self.opened()
        self.turn = session.begin_turn(answer)
        return self.scene()

    def end_turn(self, closing: Narration) -> str:
        session = self.opened()
        turn = self.started()
        lines = closing.lines
        if not lines and turn.draft.pending is None:
            raise ModelRetry(
                "write the narration lines: a turn with neither prose nor an open "
                "decision shows the player nothing."
            )
        if refused := speakers_refusal(turn.engine.views(turn.draft).narrator, lines):
            raise ModelRetry(refused)
        state = session.end_turn(turn, lines)
        self.turn = None
        return f"turn {state.turn} committed."

    def call_director_tool(self, name: str, raw: dict[str, JsonValue]) -> str:
        return self.started().call(name, raw)


def _target(catalog: LauncherCatalog, slug: str) -> LaunchTarget:
    saved = next((save for save in catalog.saves if save.target.slug == slug), None)
    if saved is not None:
        return saved.target
    named = slug.split("--")
    if len(named) != 2:
        raise ModelRetry(
            f"{slug!r} is neither a save nor <scenario>--<character>.\n{_listing(catalog)}"
        )
    scenario_id, character_id = named
    try:
        return launch_target(catalog, scenario_id, character_id)
    except ValueError as unknown:
        raise ModelRetry(f"{unknown}\n{_listing(catalog)}") from unknown


def catalogue(runtime: Runtime) -> str:
    return _listing(load_catalog(runtime.settings, runtime.engines))


def _listing(catalog: LauncherCatalog) -> str:
    return "\n".join(
        (
            "saves: " + (", ".join(save.target.slug for save in catalog.saves) or "(none)"),
            "scenarios: " + ", ".join(entry.id for entry in catalog.scenarios),
            "characters: " + ", ".join(entry.id for entry in catalog.characters),
            "engines: " + ", ".join(catalog.engines),
        )
    )


def _recent(state: Game, limit: int) -> str:
    told = [
        f"> {exchange.prompt}\n[at {exchange.scene}] {exchange.narration}"
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
