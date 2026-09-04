import logging
from asyncio import get_running_loop
from collections.abc import Awaitable, Callable
from pathlib import Path
from time import monotonic

from nicegui import ui

from aidm.app.runtime import BEGUN, CROSSED, GameService, Runtime
from aidm.config import Role
from aidm.core.facts import DiceEvent, Fact, cards
from aidm.core.play import Answer, Speaker
from aidm.core.views import PlayerView
from aidm.ui.panels import journal_panel, scene_sidebar
from aidm.ui.widgets import (
    avatar,
    decision_widget,
    page_header,
    working,
)

_SCENE_HEIGHT = "calc(25vh - 1rem)"

_ART_BOX = f"flex: none; height: {_SCENE_HEIGHT}; max-width: 50%; aspect-ratio: 16 / 9"

_STEP_COPY: dict[Role, tuple[str, str]] = {
    "master": (
        "Game Master",
        "Works out what your action actually does: who reacts, what changes, "
        "and whether the dice decide it.",
    ),
    "narrator": ("Narrator", "Writes what you see and hear this turn."),
    "worldsmith": (
        "Worldsmith",
        "Writes the next scene or region, or what the game master asked for: where the story "
        "goes and who is waiting there. This one is slow; a few minutes is normal.",
    ),
}

LOGGER = logging.getLogger(__name__)


class GamePage:
    """One tab on one game: it polls the service once a second and refreshes its own panels."""

    def __init__(self, runtime: Runtime, session: GameService) -> None:
        self.runtime = runtime
        self.session = session
        self.shown_art: Path | None = None
        self.shown_clip: Path | None = None
        self.autoplay_clip: Path | None = None
        self.transcript: ui.scroll_area
        # What the last poll read: the phase, the facts landed, the exchanges filed.
        self.seen: tuple[Role | None, int, int, bool, str | None] = (None, 0, 0, False, None)
        self.step_started: float | None = None
        self.ticker: ui.label | None = None
        # The composer's widgets, built once by `composer` and set by `_set_composer`.
        self.box: ui.input
        self.send: ui.button
        self.move_on_button: ui.button
        self.over_label: ui.label

    def build(self) -> None:
        session = self.session
        if session.unopened():
            ui.timer(0.1, self._open, once=True)
        else:
            session.illustrate()
        with page_header(session.state.scenario.title, session.engine.title):
            ui.space()
            ui.button("restart", on_click=self.restart).props("flat color=white dense")

        # Account for the header and page padding so the input stays above the fold.
        with (
            ui.splitter(value=55).classes("w-full").style("height: calc(100vh - 6rem)") as splitter
        ):
            with splitter.before, ui.column().classes("w-full h-full p-4").style("gap: 0.5rem"):
                self.scene_header()
                with ui.scroll_area().classes("w-full flex-grow game-transcript") as transcript:
                    self.chat()
                    self.live_turn()
                self.decision_panel()
                self.way_on_panel()
                self.composer()
                self.transcript = transcript
                ui.timer(0.5, lambda: transcript.scroll_to(percent=1.0), once=True)
            with splitter.after, ui.column().classes("w-full h-full").style("gap: 0"):
                with ui.tabs().classes("w-full") as tabs:
                    scene_tab = ui.tab("scene")
                    journal_tab = ui.tab("journal")
                with ui.tab_panels(tabs, value=scene_tab).classes("w-full flex-grow"):
                    with ui.tab_panel(scene_tab), ui.scroll_area().classes("w-full h-full"):
                        self.sidebar()
                    with ui.tab_panel(journal_tab), ui.scroll_area().classes("w-full h-full"):
                        self.journal()

        # A cached clip never autoplays on a page load, only one landing after.
        self.shown_clip = session.newest_clip()
        self.seen = _observed(session)
        self._set_composer()

        ui.timer(1.0, self.poll_turn)
        if session.media is not None or session.reader is not None:
            ui.timer(3.0, self.poll_media)

    def refresh(self) -> None:
        self.scene_header.refresh()
        self.chat.refresh()
        self.live_turn.refresh()
        self.decision_panel.refresh()
        self.way_on_panel.refresh()
        self.sidebar.refresh()
        self.journal.refresh()

    @ui.refreshable_method
    def scene_header(self) -> None:
        session = self.session
        scene = session.engine.narrator_view(session.state)
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
                ui.label(scene.title).classes("text-h6 font-bold")
                ui.label(scene.situation).classes("text-sm opacity-70")

    @ui.refreshable_method
    def chat(self) -> None:
        session = self.session
        history = session.engine.history(session.state)
        if not history:
            ui.label(session.state.scenario.premise).classes("text-sm italic opacity-70")
        # The live decision widget sits directly below the last exchange, so it needs no pause line.
        last = history[-1] if history and session.state.pending is not None else None
        player = session.player_view().player.speaker()
        for exchange in history:
            if exchange.prompt in (BEGUN, CROSSED):
                # A turn nobody played: the story's own marker, never the player's words.
                ui.label(exchange.prompt).classes("w-full text-center text-xs italic opacity-60")
            else:
                _bubble(session, player, exchange.prompt, sent=True)
            for fact in cards(exchange.facts):
                _card(fact)
            for line in exchange.lines:
                _bubble(session, line.speaker, line.text, sent=False)
            if exchange.decision and exchange is not last:
                ui.label(f"Paused: {exchange.decision}").classes("text-xs italic opacity-60")
        # The newest clip only: every `ui.audio` registers a route, and a refresh rebuilds them all.
        if history and session.reader is not None and (clip := session.reader.clip(history[-1])):
            ui.audio(clip, autoplay=clip == self.autoplay_clip)
            # Consumed by this render: a later refresh of the same turn must not restart it.
            self.autoplay_clip = None

    @ui.refreshable_method
    def live_turn(self) -> None:
        session = self.session
        turn = session.turn
        if turn is not None:
            _bubble(session, session.player_view().player.speaker(), turn.prompt, sent=True)
            shown = cards(turn.facts)
            for fact in shown:
                _card(fact, live=fact is shown[-1])
        elif session.intent:
            _bubble(session, session.player_view().player.speaker(), session.intent, sent=True)
        self.ticker = None
        if session.phase is not None:
            elapsed = 0.0 if self.step_started is None else monotonic() - self.step_started
            self.ticker = _inline_status(session.phase, elapsed)

    @ui.refreshable_method
    def way_on_panel(self) -> None:
        """The banner, not the offer: legible after a reload, once the asking has scrolled away."""
        if not self.session.engine.ready(self.session.state):
            return
        with (
            ui.row()
            .classes("game-card game-decision w-full items-center no-wrap")
            .style("gap: 0.4rem")
        ):
            ui.icon("arrow_forward").classes("game-card-icon")
            ui.label("there is more beyond here").classes("text-xs font-bold game-outcome")
            ui.label("keep playing, or say what you pursue and press Move on").classes(
                "text-xs opacity-60"
            )

    @ui.refreshable_method
    def decision_panel(self) -> None:
        pending = self.session.player_view().prompt
        if pending is None:
            return

        async def answer(option_id: str) -> None:
            if self.refuse_play():
                return
            await self._send(Answer(option_id=option_id))

        with ui.column().classes("game-card game-decision w-full").style("gap: 0.5rem"):
            with ui.row().classes("items-center no-wrap").style("gap: 0.4rem"):
                ui.icon("pause_circle").classes("game-card-icon")
                ui.label(pending.kind).classes("text-xs font-bold game-outcome")
                ui.label("the game is waiting on you").classes("text-xs opacity-60")
            decision_widget(pending.prompt, pending.options, answer)
            if pending.allows_text:
                pointer = "Or answer" if pending.options else "Answer"
                ui.label(f"{pointer} in your own words below.").classes("text-xs opacity-60")

    @ui.refreshable_method
    def sidebar(self) -> None:
        scene_sidebar(self.session, self.move_on)

    @ui.refreshable_method
    def journal(self) -> None:
        journal_panel(self.session)

    def composer(self) -> None:
        with (
            ui.row().classes("w-full no-wrap items-end game-composer q-pa-sm").style("gap: 0.5rem")
        ):
            self.over_label = (
                ui.label("").classes("text-xs self-center").style("color: var(--game-danger)")
            )
            self.box = (
                ui.input().classes("flex-grow").props("outlined autogrow type=textarea borderless")
            )
            # Enter sends; without the prevent the browser also leaves its newline behind.
            self.box.on(
                "keydown.enter",
                self.submit,
                js_handler="(e) => { if (e.shiftKey) return; e.preventDefault(); emit(); }",
            )
            self.send = ui.button(icon="send", on_click=self.submit).props("round flat")
            self.move_on_button = ui.button(
                "Move on", icon="arrow_forward", on_click=lambda: self.submit(moving_on=True)
            ).props("no-caps outline dense")

    def poll_turn(self) -> None:
        """The page reads the turn once a second; the turn never calls the page."""
        now = _observed(self.session)
        if now[0] != self.seen[0]:
            self.step_started = None if now[0] is None else monotonic()
        if now != self.seen:
            self.seen = now
            self._set_composer()
            self.refresh()
            self._scroll()
        ticker, started = self.ticker, self.step_started
        if ticker is not None and started is not None and not ticker.is_deleted:
            ticker.set_text(_clock(monotonic() - started))

    def poll_media(self) -> None:
        """The illustration and the clip are generated after the turn commits and watched for."""
        session = self.session
        art = session.scene_art()
        if art != self.shown_art:
            self.shown_art = art
            self.scene_header.refresh()
        clip = session.newest_clip()
        if clip != self.shown_clip:
            self.shown_clip = clip
            if clip is not None:
                self.autoplay_clip = clip
            self.chat.refresh()

    def refuse_play(self) -> bool:
        refusal = self.runtime.play_refusal(self.session)
        if refusal is None:
            return False
        ui.notify(refusal, type="warning")
        return True

    async def submit(self, moving_on: bool = False) -> None:
        box = self.box
        typed = (box.value or "").strip()
        LOGGER.info("player submitted prompt: non_empty=%s busy=%s", bool(typed), self.session.busy)
        if not typed or self.refuse_play():
            return
        box.value = ""
        # Quasar never saw the typed value change, so only an explicit push empties the composer.
        box.run_method("updateValue")
        await self._send(Answer(text=typed), moving_on=moving_on)

    async def move_on(self, intent: str) -> None:
        if self.refuse_play():
            return
        pending = self.session.player_view().prompt
        if pending is not None and not pending.allows_text:
            ui.notify("Choose an option above.", type="warning")
            return
        await self._send(Answer(text=intent), moving_on=True)

    async def restart(self) -> None:
        if self.refuse_play():
            return
        self.session.restart()
        self.poll_turn()
        await self._open()

    def _set_composer(self) -> None:
        """One `player_view()` sets the four widgets; the poll calls it when the turn moved."""
        session = self.session
        player = session.player_view()
        typing = _can_type(player, session.phase)
        self.box.set_enabled(typing)
        self.send.set_enabled(typing)
        self.move_on_button.set_enabled(typing)
        self.move_on_button.set_visibility(session.engine.ready(session.state))
        self.over_label.set_text(player.over or "")
        self.box.props(f'placeholder="{_placeholder(player, session.phase)}"')

    def _scroll(self) -> None:
        # A method call on an existing element needs no NiceGUI slot; `ui.timer` here would.
        get_running_loop().call_later(0.1, lambda: self.transcript.scroll_to(percent=1.0))

    async def _run(self, playing: Callable[[], Awaitable[None]]) -> None:
        """The composer greys at once, not at the next tick: a second Enter has nothing to hit."""
        for widget in (self.box, self.send, self.move_on_button):
            widget.set_enabled(False)
        try:
            async with working():
                await playing()
        finally:
            self._set_composer()
            self.poll_turn()

    async def _open(self) -> None:
        # A second tab's timer must not run the page reset over an opening already in flight.
        if not self.session.unopened():
            return
        await self._run(self.session.open)

    async def _send(self, answer: Answer, *, moving_on: bool = False) -> None:
        await self._run(lambda: self.session.play(answer, moving_on=moving_on))


def game_page(runtime: Runtime, session: GameService) -> None:
    GamePage(runtime, session).build()


def _scene_art(session: GameService) -> None:
    art = session.scene_art()
    if art is not None:
        # `contain` letterboxes a frame drawn at another ratio instead of cropping its subject.
        ui.image(art).props("fit=contain").classes("rounded-borders").style(_ART_BOX)


def _card(fact: Fact, *, live: bool = False) -> None:
    headline, *detail = fact.card.split("\n")
    with ui.column().classes("game-card w-full").style("gap: 0.3rem"):
        ui.label(headline).classes("text-sm font-bold")
        for line in detail:
            ui.label(line).classes("text-xs opacity-80")
        if fact.dice:
            with ui.row().classes("items-start").style("gap: 1rem"):
                for group in fact.dice:
                    _dice_group(group, live=live)


def _dice_group(die: DiceEvent, *, live: bool) -> None:
    with ui.column().style("gap: 0.2rem"):
        ui.label(die.label).classes("text-xs opacity-60")
        with ui.row().classes("no-wrap").style("gap: 0.3rem"):
            for index, (face, value) in enumerate(zip(die.faces, die.rolled, strict=True)):
                with (
                    ui.column()
                    .classes(
                        "game-die"
                        + (" game-die-kept" if index in die.highlight else "")
                        + (" game-die-live" if live else "")
                    )
                    .style("gap: 0")
                ):
                    ui.label(f"d{face}").classes("game-die-face")
                    ui.label(str(value)).classes("game-die-value")


def _bubble(session: GameService, speaker: Speaker | None, text: str, *, sent: bool) -> None:
    icon = None if speaker is None else session.icon(speaker.id)
    name = "DM" if speaker is None else speaker.name
    message = ui.chat_message(text, name=name, sent=sent).classes("w-full")
    if speaker is None:
        message.props("bg-color=grey-3")
    with message.add_slot("avatar"):
        avatar(icon, None if speaker is None else name)


def _inline_status(step: Role, elapsed: float) -> ui.label:
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


def _observed(session: GameService) -> tuple[Role | None, int, int, bool, str | None]:
    """Phase, facts landed, exchanges filed, the way on, the end: what a render reads."""
    turn = session.turn
    return (
        session.phase,
        0 if turn is None else len(turn.facts),
        len(session.engine.history(session.state)),
        session.engine.ready(session.state),
        session.player_view().over,
    )


def _can_type(player: PlayerView, phase: Role | None) -> bool:
    """The composer opens between turns, unless the game waits on a pick or is over."""
    prompt = player.prompt
    return phase is None and (prompt is None or prompt.allows_text) and player.over is None


def _placeholder(player: PlayerView, phase: Role | None) -> str:
    if phase is not None:
        return f"{_STEP_COPY[phase][0]} is working..."
    if player.prompt is None:
        return "What do you do?"
    if player.prompt.allows_text:
        return "The game is waiting on your answer."
    return "Choose an option above."
