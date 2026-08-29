import logging
from asyncio import AbstractEventLoop, get_running_loop
from collections.abc import Callable, Sequence
from functools import partial
from pathlib import Path
from time import monotonic

from nicegui import ui
from pydantic import JsonValue

from aidm.app.runtime import GameSession
from aidm.harness.driver import Driver
from aidm.state.entities import DEAD, Entity, EntityId
from aidm.state.facts import DiceEvent, Fact
from aidm.state.play import Answer
from aidm.turn.context import player_scene
from aidm.turn.run import TurnStep

from .panels import journal_panel, sheet_panel, state_panel, trace_panel
from .widgets import (
    avatar,
    decision_widget,
    entity_row,
    heading,
    page_header,
    refuse_if_busy,
    working,
)

_SCENE_HEIGHT = "calc(25vh - 1rem)"


_ART_BOX = f"flex: none; height: {_SCENE_HEIGHT}; max-width: 50%; aspect-ratio: 16 / 9"


def scene_header(session: GameSession, fill_composer: Callable[[str], None]) -> None:
    scene = player_scene(session.state)
    # A quarter of the column at most: the art holds it and the text beside it scrolls.
    with (
        ui.row()
        .classes("w-full items-start no-wrap")
        .style(f"max-height: {_SCENE_HEIGHT}; overflow: hidden; gap: 0.75rem")
    ):
        _scene_art(session)
        with (
            ui.column()
            .classes("flex-grow")
            .style(f"max-height: {_SCENE_HEIGHT}; overflow-y: auto; gap: 0; min-width: 0")
        ):
            ui.label(scene.location.name).classes("text-h6 font-bold")
            ui.label(scene.location.brief).classes("text-sm opacity-70")
            heading("Here now", tight=True)
            if not scene.here:
                ui.label("Nobody but you.").classes("text-sm opacity-70")
            for entity in scene.here:
                brief = entity.brief if _alive(entity) else f"Dead. {entity.brief}"
                entity_row(session.icon(entity.id), entity.name, brief)
            heading("Exits", tight=True)
            if not scene.exits:
                ui.label("None found yet.").classes("text-sm opacity-70")
            for way in scene.exits:
                name = scene.canon[way.to].name
                # The button writes the move into the composer; the player still sends it.
                ui.button(
                    name,
                    icon="lock" if way.locked else "arrow_forward",
                    on_click=lambda name=name: fill_composer(f"Go to {name}"),
                ).props("flat dense no-caps align=left rounded").classes("w-full")


def _scene_art(session: GameSession) -> None:
    art = session.scene_art()
    if art is not None:
        # `contain` letterboxes a frame drawn at another ratio instead of cropping its subject.
        ui.image(art).props("fit=contain").classes("rounded-borders").style(_ART_BOX)
    elif session.scene_pending():
        ui.skeleton().classes("rounded-borders").style(_ART_BOX)


def chat(session: GameSession) -> None:
    if not session.state.history:
        ui.label(session.state.scenario.premise).classes("text-sm italic opacity-70")
    here = ""
    history = session.state.history
    last = history[-1] if history and session.state.pending is not None else None
    for exchange in history:
        if exchange.place != here:
            here = exchange.place
            ui.label(here).classes("w-full text-center text-xs uppercase opacity-50 q-mt-md")
        _bubble(session, session.state.player_id, exchange.prompt, sent=True)
        for fact in exchange.facts:
            _card(fact)
        for line in exchange.lines:
            _bubble(session, line.speaker_id, line.text, sent=False)
        if exchange.decision and exchange is not last:
            ui.label(f"Paused: {exchange.decision}").classes("text-xs italic opacity-60")


def _card(fact: Fact) -> None:
    headline, *detail = fact.card.split("\n")
    with ui.column().classes("game-card w-full").style("gap: 0.3rem"):
        ui.label(headline).classes("text-sm font-bold")
        for line in detail:
            ui.label(line).classes("text-xs opacity-80")
        if fact.dice:
            with ui.row().classes("items-start").style("gap: 1rem"):
                for group in fact.dice:
                    _dice_group(group)


def _dice_group(die: DiceEvent) -> None:
    with ui.column().style("gap: 0.2rem"):
        ui.label(die.label).classes("text-xs opacity-60")
        with ui.row().classes("no-wrap").style("gap: 0.3rem"):
            for index, (face, value) in enumerate(zip(die.faces, die.rolled, strict=True)):
                with (
                    ui.column()
                    .classes("game-die" + (" game-die-kept" if index in die.highlight else ""))
                    .style("gap: 0")
                ):
                    ui.label(f"d{face}").classes("game-die-face")
                    ui.label(str(value)).classes("game-die-value")


def _bubble(session: GameSession, speaker_id: EntityId | None, text: str, *, sent: bool) -> None:
    speaker = None if speaker_id is None else session.state.world.require(speaker_id)
    icon = None if speaker_id is None else session.icon(speaker_id)
    name = "DM" if speaker is None else speaker.name
    message = ui.chat_message(text, name=name, sent=sent).classes("w-full")
    if speaker is None:
        message.props("bg-color=grey-3")
    with message.add_slot("avatar"):
        avatar(icon, None if speaker is None else name)


_STEP_COPY: dict[TurnStep, tuple[str, str]] = {
    "director": (
        "Director",
        "Works out what your action actually does: who reacts, what changes, "
        "and whether the dice decide it.",
    ),
    "narrator": ("Narrator", "Writes what you see and hear this turn."),
    "scenario_creator": (
        "Worldsmith",
        "Writes new places and people into the world, because it was running out of somewhere "
        "for you to go. This one is slow — a few minutes is normal.",
    ),
}


def live_turn(
    session: GameSession, prompt: str | None, facts: Sequence[Fact], elapsed: float
) -> ui.label | None:
    if prompt is not None:
        _bubble(session, session.state.player_id, prompt, sent=True)
    for fact in facts:
        _card(fact)
    if session.step is not None:
        return _inline_status(session.step, elapsed)
    return None


def _inline_status(step: TurnStep, elapsed: float) -> ui.label:
    label, description = _STEP_COPY[step]
    with ui.row().classes("items-center no-wrap q-py-xs").style("gap: 0.4rem"):
        ui.spinner(size="1.1rem")
        ui.label(label).classes("text-sm font-bold")
        ticker = ui.label(_clock(elapsed)).classes("text-xs font-mono")
    if description:
        ui.label(description).classes("text-xs opacity-70")
    return ticker


def _clock(seconds: float) -> str:
    minutes, rest = divmod(int(seconds), 60)
    return f"{minutes}:{rest:02d}"


LOGGER = logging.getLogger(__name__)


class GameView:
    def __init__(self, session: GameSession, driver: Driver | None = None) -> None:
        self.session = session
        self.driver = driver
        self.agent_log: ui.log | None = None
        self.shown_art: tuple[Path | None, bool] = (None, False)
        # Both are built by the page below this view, and the panels reach them through it.
        self.composer: ui.input | None = None
        self.transcript: ui.scroll_area | None = None
        # The turn in flight, owned by the view, never by game state; cleared on success or failure.
        self.live_prompt: str | None = None
        self.live_facts: list[Fact] = []
        self.step_started: float | None = None
        self.ticker: ui.label | None = None

    @property
    def viewing(self) -> bool:
        """An agent you start yourself writes the save from another process; this only shows it."""
        return self.session.settings.harness == "external"

    def log(self, line: str) -> None:
        if self.agent_log is not None and not self.agent_log.is_deleted:
            self.agent_log.push(line)

    def fill_composer(self, text: str) -> None:
        if self.composer is not None:
            self.composer.value = text

    @ui.refreshable_method
    def scene(self) -> None:
        scene_header(self.session, self.fill_composer)

    @ui.refreshable_method
    def chat(self) -> None:
        chat(self.session)

    @ui.refreshable_method
    def live_turn(self) -> None:
        elapsed = 0.0 if self.step_started is None else monotonic() - self.step_started
        self.ticker = live_turn(self.session, self.live_prompt, self.live_facts, elapsed)

    @ui.refreshable_method
    def decision(self) -> None:
        decision_panel(self)

    @ui.refreshable_method
    def sheet(self) -> None:
        sheet_panel(self.session)
        player_actions(self)

    @ui.refreshable_method
    def journal(self) -> None:
        journal_panel(self.session)

    @ui.refreshable_method
    def trace(self) -> None:
        trace_panel(self.session)

    @ui.refreshable_method
    def state(self) -> None:
        state_panel(self.session)

    def refresh_all(self) -> None:
        for panel in (
            self.scene,
            self.chat,
            self.live_turn,
            self.decision,
            self.sheet,
            self.journal,
            self.trace,
            self.state,
        ):
            panel.refresh()


def _composer_placeholder(view: GameView) -> str:
    step = view.session.step
    if step is not None:
        return f"{_STEP_COPY[step][0]} is working..."
    pending = view.session.state.pending
    if pending is not None:
        if not pending.allows_text:
            return "Choose an option above."
        return "The game is waiting on your answer."
    return "What do you do?"


def on_step(view: GameView, step: TurnStep) -> None:
    view.session.step = step
    view.step_started = monotonic()
    view.live_turn.refresh()
    if view.composer is not None:
        view.composer.props(f'placeholder="{_composer_placeholder(view)}"')


def on_fact(view: GameView, fact: Fact, loop: AbstractEventLoop) -> None:
    """Schedule refreshes on NiceGUI's loop because sync tools emit from worker threads."""
    loop.call_soon_threadsafe(_apply_fact, view, fact)


def _apply_fact(view: GameView, fact: Fact) -> None:
    if not (fact.told and fact.card):
        return
    view.live_facts.append(fact)
    view.live_turn.refresh()
    _scroll(view)


def _scroll(view: GameView) -> None:
    if (transcript := view.transcript) is not None:
        # A method call on an existing element needs no NiceGUI slot; `ui.timer` here would.
        get_running_loop().call_later(0.1, lambda: transcript.scroll_to(percent=1.0))


def tick_elapsed(view: GameView) -> None:
    """The timer lives on the page, not in the refreshable."""
    ticker, started = view.ticker, view.step_started
    if ticker is not None and started is not None and not ticker.is_deleted:
        ticker.set_text(_clock(monotonic() - started))


def poll_art(view: GameView) -> None:
    """The illustration is generated after the turn commits, so the page watches for it to land."""
    shown = (view.session.scene_art(), view.session.scene_pending())
    if shown != view.shown_art:
        view.shown_art = shown
        view.scene.refresh()


async def _send(view: GameView, player_input: str | Answer, bubble: str) -> None:
    session = view.session
    view.live_prompt, view.live_facts = bubble, []
    view.live_turn.refresh()
    _scroll(view)
    async with working(session):
        if view.driver is not None:
            await _play_with_agent(view, view.driver, player_input, bubble)
        else:
            loop = get_running_loop()
            await session.submit(
                player_input,
                on_step=lambda step: on_step(view, step),
                on_fact=lambda fact: on_fact(view, fact, loop),
            )
    session.step = None
    view.live_prompt, view.live_facts, view.step_started = None, [], None
    if view.composer is not None:
        view.composer.props(f'placeholder="{_composer_placeholder(view)}"')
    view.refresh_all()
    _scroll(view)


async def _play_with_agent(
    view: GameView, driver: Driver, player_input: str | Answer, bubble: str
) -> None:
    """The agent commits through the MCP tools, so each message it sends is a cue to redraw."""
    session = view.session
    on_step(view, "director")
    committed = len(session.state.history)
    # `start_turn` takes the chosen option by id, and only the text reaches the agent.
    chose = player_input.option_id if isinstance(player_input, Answer) else None
    text = bubble if chose is None else f"{bubble} (option_id: {chose})"
    async for line in driver.play(text):
        view.log(line)
        # A CLI the app spawned commits from its own process, so the save is the only channel.
        poll_save(view)
        view.live_facts = list(session.state.turn_facts)
        if len(session.state.history) > committed:
            # `end_turn` wrote the real bubble; the live one would now be a second copy.
            view.live_prompt = None
        view.refresh_all()


async def submit(view: GameView, box: ui.input) -> None:
    session = view.session
    typed = (box.value or "").strip()
    LOGGER.info("player submitted prompt: non_empty=%s busy=%s", bool(typed), session.busy)
    if not typed or refuse_if_busy(session):
        return
    box.value = ""
    # Quasar never saw the typed value change, so only an explicit push empties the composer.
    _ = box.run_method("updateValue")
    typed_input = typed if session.state.pending is None else Answer(text=typed)
    await _send(view, typed_input, typed)


def _alive(entity: Entity) -> bool:
    return entity.trait(DEAD) is None


def _can_type(session: GameSession, busy: bool) -> bool:
    pending = session.state.pending
    typed = pending is None or pending.allows_text
    return not busy and typed and _alive(session.state.player)


def decision_panel(view: GameView) -> None:
    pending = view.session.state.pending
    if pending is None:
        return

    labels = {option.id: option.label for option in pending.options}

    async def answer(option_id: str) -> None:
        if refuse_if_busy(view.session):
            return
        await _send(view, Answer(option_id=option_id), labels[option_id])

    with ui.column().classes("game-card game-decision w-full").style("gap: 0.5rem"):
        with ui.row().classes("items-center no-wrap").style("gap: 0.4rem"):
            ui.icon("pause_circle").classes("game-card-icon")
            ui.label(pending.kind).classes("text-xs font-bold game-outcome")
            ui.label("the game is waiting on you").classes("text-xs opacity-60")
        decision_widget(pending.prompt, () if view.viewing else pending.options, answer)
        if view.viewing:
            ui.label("Answer in the terminal.").classes("text-sm opacity-60")
            return
        # A dead player character answers by taking a successor's name, never in their own words.
        if pending.allows_text and _alive(view.session.state.player):
            pointer = "Or answer" if pending.options else "Answer"
            ui.label(f"{pointer} in your own words below.").classes("text-xs opacity-60")


def player_actions(view: GameView) -> None:
    session = view.session
    # Code mode plays in another process that holds its own state; a write here would race it.
    if session.stages is None:
        return
    offers = session.offers()
    if not offers:
        return
    heading("You can")
    with ui.row().classes("w-full items-center").style("gap: 0.5rem"):
        for action, offer in offers:
            ui.button(offer.label, on_click=partial(_act, view, action.name, offer.args)).props(
                "no-caps outline dense"
            ).tooltip(action.description)


async def _act(view: GameView, name: str, args: dict[str, JsonValue]) -> None:
    if refuse_if_busy(view.session):
        return
    async with working(view.session):
        _ = view.session.act(name, args)
    view.refresh_all()
    _scroll(view)


def composer(view: GameView) -> None:
    session = view.session
    with ui.row().classes("w-full no-wrap items-end game-composer q-pa-sm").style("gap: 0.5rem"):
        # `busy` is only the source NiceGUI needs: it re-runs every backward on its 0.1s poll.
        ui.label("You died.").classes("text-xs self-center").style(
            "color: var(--game-danger)"
        ).bind_visibility_from(session, "busy", backward=lambda _: not _alive(session.state.player))
        box = (
            ui.input(placeholder=_composer_placeholder(view))
            .classes("flex-grow")
            .props("outlined autogrow type=textarea borderless")
            .bind_enabled_from(session, "busy", backward=partial(_can_type, session))
        )
        # Enter sends; without the prevent the browser also leaves its newline behind.
        box.on(
            "keydown.enter",
            lambda: submit(view, box),
            js_handler="(e) => { if (e.shiftKey) return; e.preventDefault(); emit(); }",
        )
        _ = (
            ui.button(icon="send", on_click=lambda: submit(view, box))
            .props("round flat")
            .bind_enabled_from(session, "busy", backward=partial(_can_type, session))
        )
        if (driver := view.driver) is not None:
            ui.button(icon="stop", on_click=driver.interrupt).props("round flat").tooltip(
                "Stop the agent"
            ).bind_visibility_from(session, "busy")
    view.composer = box


def poll_save(view: GameView) -> None:
    """The turn commits in another process, so the viewer watches the save file for it to land."""
    if view.session.reload():
        view.session.illustrate_scene()
        view.refresh_all()


def restart(view: GameView) -> None:
    session = view.session
    if refuse_if_busy(session):
        return
    session.restart()
    view.live_prompt, view.live_facts = None, []
    view.refresh_all()


def game_page(session: GameSession, driver: Driver | None = None) -> None:
    session.illustrate_scene()
    view = GameView(session, driver)
    with page_header(session.state.scenario.title, session.engine.badge):
        ui.space()
        if not view.viewing:
            ui.button("restart", on_click=lambda: restart(view)).props("flat color=white dense")

    # Account for the header and page padding so the input stays above the fold.
    with ui.splitter(value=55).classes("w-full").style("height: calc(100vh - 6rem)") as splitter:
        with splitter.before, ui.column().classes("w-full h-full p-4").style("gap: 0.5rem"):
            view.scene()
            with ui.scroll_area().classes("w-full flex-grow game-transcript") as transcript:
                view.chat()
                view.live_turn()
            view.decision()
            if view.viewing:
                ui.label("Played in the terminal; this window follows along.").classes(
                    "w-full text-xs opacity-60 q-pa-sm"
                )
            else:
                composer(view)
            view.transcript = transcript
        with splitter.after, ui.column().classes("w-full h-full").style("gap: 0"):
            with ui.tabs().classes("w-full") as tabs:
                scene_tab = ui.tab("scene")
                journal_tab = ui.tab("journal")
                dev_tab = ui.tab("dev", icon="code").classes("game-dev-tab")
            with ui.tab_panels(tabs, value=scene_tab).classes("w-full flex-grow"):
                with ui.tab_panel(scene_tab), ui.scroll_area().classes("w-full h-full"):
                    view.sheet()
                with ui.tab_panel(journal_tab), ui.scroll_area().classes("w-full h-full"):
                    view.journal()
                with ui.tab_panel(dev_tab), ui.scroll_area().classes("w-full h-full"):
                    with ui.expansion("trace", value=True).classes("w-full"):
                        view.trace()
                    with ui.expansion("state").classes("w-full"):
                        view.state()
                    if driver is not None:
                        with ui.expansion("agent", value=True).classes("w-full"):
                            view.agent_log = ui.log(max_lines=500).classes("w-full h-64 text-xs")

    ui.timer(1.0, lambda: tick_elapsed(view))
    if session.settings.code_mode:
        # `external` depends on this; under `claude` it only catches a turn whose stream was lost.
        ui.timer(2.0, lambda: poll_save(view))
    if session.media is not None:
        ui.timer(3.0, lambda: poll_art(view))
