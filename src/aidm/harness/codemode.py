import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ConfigDict, JsonValue
from pydantic_ai import ModelRetry

from aidm.app.launch import (
    LauncherCatalog,
    LauncherController,
    LaunchTarget,
    as_engine_id,
    load_catalog,
)
from aidm.app.runtime import DraftedAdvance, GameSession, Runtime
from aidm.authoring.run import (
    AuthoringRun,
    GrowthRun,
    ScenarioRun,
    authoring_context,
    briefing,
    growth_run,
    scenario_run,
)
from aidm.config import Settings
from aidm.engines.core import DirectorContext, ProposalBase, TurnRecord, run_command
from aidm.engines.world import commands
from aidm.state.entities import CheckedEntityId, EngineId, Frozen, Slug
from aidm.state.facts import traced
from aidm.state.model import Game
from aidm.state.play import (
    Answer,
    Line,
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
from aidm.turn.run import close_segment, consume_answer, speakers_refusal

LOGGER = logging.getLogger(__name__)

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


class StartTurn(ToolArgs):
    prompt: str
    """What the player did, in their words."""
    option_id: Slug | None = None
    """Exact id of the listed option their words chose, when a decision is open."""


class EndTurn(ToolArgs):
    lines: tuple[Line, ...]
    """The prose the player reads, in order."""


class AdvanceArgs[P: ProposalBase](ToolArgs):
    subject_id: CheckedEntityId
    """Exact id of the character the offer names."""
    proposal: P
    """The change to draft, in this engine's own vocabulary."""


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
    turn: Turn | None = None
    authoring: AuthoringRun | None = None

    def opened(self) -> GameSession:
        if self.session is None:
            raise ModelRetry(
                f"no game is open; call open_game(slug) first.\n{catalogue(self.settings)}"
            )
        return self.session

    def started(self) -> Turn:
        if self.turn is None:
            raise ModelRetry("no turn is open; call start_turn with the player's message first.")
        return self.turn

    def open_game(self, slug: str) -> str:
        target = _target(load_catalog(self.settings), slug)
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
        rules = f"{PREAMBLE}\n{director_instructions(engine.director_instructions)}\n\n{NARRATOR}"
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

    def call_director_tool(self, name: str, raw: dict[str, JsonValue]) -> str:
        session = self.opened()
        turn = self.started()
        found = next((one for one in commands(session.engine) if one.name == name), None)
        if found is None:
            raise ModelRetry(f"{name!r} is not a command of the {session.engine.id!r} engine.")
        deps = DirectorContext(
            engine=session.engine,
            draft=session.state.draft(),
            rng=session.rng,
            log=turn.log,
            suspended_at_start=turn.suspended_at_start,
            answered=turn.answered,
        )
        answered = run_command(found, deps, raw)
        session.commit(deps.draft.committed())
        return answered

    def advance_args(self) -> type[AdvanceArgs[ProposalBase]]:
        return AdvanceArgs[self.opened().engine.advancement.proposal_type]

    def propose_advance(self, raw: dict[str, JsonValue]) -> str:
        session = self.opened()
        advancement = session.engine.advancement
        asked = self.advance_args().model_validate(raw)
        offer = next((one for one in session.offers() if one.subject_id == asked.subject_id), None)
        if offer is None:
            raise ModelRetry(f"nothing is on offer for {asked.subject_id!r}.")
        # The same refusal the builtin advisor retries against, run here against live state.
        if refused := advancement.advance_refusal(session.state, offer, asked.proposal):
            raise ModelRetry(refused)
        drafted = DraftedAdvance(offer=offer, proposal=asked.proposal)
        session.drafted = drafted
        return (
            f"proposed for {asked.subject_id}:\n{traced(session.preview(drafted))}\n"
            "Show the player, then call apply_advance() if they accept."
        )

    def apply_advance(self) -> str:
        session = self.opened()
        drafted = session.drafted
        if drafted is None:
            raise ModelRetry("nothing is drafted; call propose_advance first.")
        landed = session.apply_proposal(drafted)
        session.drafted = None
        return traced(landed)

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
        ctx = authoring_context(run.draft, name)
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
        return f"{summary}\n{traced(landed)}"

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


def catalogue(settings: Settings) -> str:
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
    return (
        f"{pending.kind}: {pending.prompt}\n"
        f"{options or '- (the player answers in their own words)'}"
    )


def _offers(session: GameSession) -> str:
    """The offer's rules text rides along: it is what an advance may buy under this engine."""
    listed = [
        f"- {offer.subject_id}: {offer.prompt}" + (f"\n{offer.text}" if offer.text else "")
        for offer in session.offers()
    ]
    return "\n".join(listed) or "- (none)"
