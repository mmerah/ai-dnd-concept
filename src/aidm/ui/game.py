import logging
from asyncio import get_running_loop
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from time import monotonic
from typing import Self

from nicegui import ui

from aidm.app.runtime import MARKS, GameService, Runtime
from aidm.config import Role
from aidm.core.entities import EntityId
from aidm.core.facts import DiceEvent, Fact, cards
from aidm.core.play import Answer
from aidm.core.views import Action, PlayerView
from aidm.ui.widgets import (
    avatar,
    decision_widget,
    entity_row,
    heading,
    labeled_value,
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


@dataclass(frozen=True, slots=True)
class Observed:
    phase: Role | None
    facts: int
    exchanges: int
    action: Action | None
    over: str | None

    @classmethod
    def of(cls, session: GameService) -> Self:
        view = session.player_view()
        return cls(
            session.phase,
            0 if session.turn is None else len(session.turn.facts),
            len(session.engine.history(session.state)),
            view.action,
            view.over,
        )


class GamePage:
    """One tab on one game: it polls the service once a second and refreshes its own panels."""

    def __init__(self, runtime: Runtime, session: GameService) -> None:
        self.runtime = runtime
        self.session = session
        self.shown_art: Path | None = None
        self.shown_clip: Path | None = None
        self.autoplay_clip: Path | None = None
        self.transcript: ui.scroll_area
        self.seen: Observed = Observed(None, 0, 0, None, None)
        self.step_started: float | None = None
        self.ticker: ui.label | None = None
        self.box: ui.input
        self.send: ui.button
        self.action_button: ui.button
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
        self.seen = Observed.of(session)
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
            if (art := session.scene_art()) is not None:
                # `contain` letterboxes a frame drawn at another ratio rather than cropping it.
                ui.image(art).props("fit=contain").classes("rounded-borders").style(_ART_BOX)
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
        player = session.player_view().player
        for exchange in history:
            if exchange.prompt in MARKS:
                # A turn nobody played: the story's own marker, never the player's words.
                ui.label(exchange.prompt).classes("w-full text-center text-xs italic opacity-60")
            else:
                _bubble(session, player.id, player.name, exchange.prompt, sent=True)
            for fact in cards(exchange.facts):
                _card(fact)
            for line in exchange.lines:
                _bubble(session, line.speaker_id, line.speaker, line.text, sent=False)
            if exchange.decision and exchange is not last:
                ui.label(f"Paused: {exchange.decision}").classes("text-xs italic opacity-60")
        # The newest clip only: every `ui.audio` registers a route, and a refresh rebuilds them all.
        if clip := session.newest_clip():
            ui.audio(clip, autoplay=clip == self.autoplay_clip)
            # Consumed by this render: a later refresh of the same turn must not restart it.
            self.autoplay_clip = None

    @ui.refreshable_method
    def live_turn(self) -> None:
        session = self.session
        turn = session.turn
        player = session.player_view().player
        if turn is not None:
            _bubble(session, player.id, player.name, turn.prompt, sent=True)
            shown = cards(turn.facts)
            for fact in shown:
                _card(fact, live=fact is shown[-1])
        elif session.intent:
            _bubble(session, player.id, player.name, session.intent, sent=True)
        self.ticker = None
        if session.phase is not None:
            elapsed = 0.0 if self.step_started is None else monotonic() - self.step_started
            self.ticker = _inline_status(session.phase, elapsed)

    @ui.refreshable_method
    def way_on_panel(self) -> None:
        """The banner: legible after a reload, once the asking has scrolled away."""
        action = self.session.player_view().action
        if action is None:
            return
        with (
            ui.row()
            .classes("game-card game-decision w-full items-center no-wrap")
            .style("gap: 0.4rem")
        ):
            ui.icon("arrow_forward").classes("game-card-icon")
            ui.label("there is more beyond here").classes("text-xs font-bold game-outcome")
            if action.intent:
                ui.button(action.label, on_click=partial(self.take, action)).props(
                    "no-caps outline dense"
                )
                ui.label(action.intent).classes("text-xs opacity-70")
            else:
                ui.label(f"{action.detail} Press {action.label} with your words.").classes(
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
            await self._run(lambda: self.session.play(Answer(option_id=option_id)))

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
        session = self.session
        view = session.player_view()
        with ui.column().classes("w-full").style("gap: 0.75rem"):
            for panel in view.panels:
                with ui.column().classes("game-card w-full"):
                    heading(panel.title, tight=True)
                    if not panel.rows:
                        ui.label("nothing").classes("text-sm opacity-60 mt-2")
                    for row in panel.rows:
                        if row.icon_id is not None:
                            entity_row(session.icon(row.icon_id), row.label, row.detail)
                        elif row.detail:
                            labeled_value(row.label, row.detail)
                        else:
                            ui.label(row.label).classes("text-sm mt-1")

    @ui.refreshable_method
    def journal(self) -> None:
        session = self.session
        heading("Chronicle")
        played = session.engine.history(session.state)
        for number, exchange in reversed(list(enumerate(played, start=1))):
            with ui.expansion(f"turn {number}: {exchange.prompt}").classes("w-full"):
                # A speaker is named, because a bare quote reads as narration without bubbles.
                for line in exchange.lines:
                    text = (
                        line.text if line.speaker_id is None else f"**{line.speaker}:** {line.text}"
                    )
                    ui.markdown(text).classes("text-sm")

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
            self.action_button = ui.button(
                icon="arrow_forward", on_click=lambda: self.submit(acting=True)
            ).props("no-caps outline dense")

    def poll_turn(self) -> None:
        """The page reads the turn once a second; the turn never calls the page."""
        now = Observed.of(self.session)
        if now.phase != self.seen.phase:
            self.step_started = None if now.phase is None else monotonic()
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

    async def submit(self, acting: bool = False) -> None:
        box = self.box
        typed = (box.value or "").strip()
        LOGGER.info("player submitted prompt: non_empty=%s busy=%s", bool(typed), self.session.busy)
        if not typed or self.refuse_play():
            return
        action = self.session.player_view().action
        if acting and action is None:
            ui.notify("The way on has changed.", type="warning")
            return
        box.value = ""
        # Quasar never saw the typed value change, so only an explicit push empties the composer.
        box.run_method("updateValue")
        if acting and action is not None:
            await self._run(lambda: self.session.act(action.id, typed))
        else:
            await self._run(lambda: self.session.play(Answer(text=typed)))

    async def take(self, action: Action) -> None:
        """The action the rules already resolved: its own words go, and the page asks for none."""
        if self.refuse_play():
            return
        await self._run(lambda: self.session.act(action.id, action.intent))

    async def restart(self) -> None:
        if self.refuse_play():
            return
        self.session.restart()
        self.poll_turn()
        await self._open()

    def _set_composer(self) -> None:
        session = self.session
        player = session.player_view()
        typing = can_type(player, session.phase)
        self.box.set_enabled(typing)
        self.send.set_enabled(typing)
        action = player.action
        self.action_button.set_enabled(typing)
        self.action_button.set_visibility(action is not None and not action.intent)
        self.action_button.set_text("" if action is None else action.label)
        self.over_label.set_text(player.over or "")
        self.box.props(f'placeholder="{_placeholder(player, session.phase)}"')

    def _scroll(self) -> None:
        # A method call on an existing element needs no NiceGUI slot; `ui.timer` here would.
        get_running_loop().call_later(0.1, lambda: self.transcript.scroll_to(percent=1.0))

    async def _run(self, playing: Callable[[], Awaitable[None]]) -> None:
        """The composer greys at once, not at the next tick: a second Enter has nothing to hit."""
        for widget in (self.box, self.send, self.action_button):
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


def game_page(runtime: Runtime, session: GameService) -> None:
    GamePage(runtime, session).build()


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


def _bubble(
    session: GameService, speaker_id: EntityId | None, name: str, text: str, *, sent: bool
) -> None:
    narration = speaker_id is None
    icon = None if narration else session.icon(speaker_id)
    chat_name = "DM" if narration else name
    message = ui.chat_message(text, name=chat_name, sent=sent).classes("w-full")
    if narration:
        message.props("bg-color=grey-3")
    with message.add_slot("avatar"):
        avatar(icon, None if narration else chat_name)


def _inline_status(step: Role, elapsed: float) -> ui.label:
    label, description = _STEP_COPY[step]
    with ui.row().classes("items-center no-wrap q-py-xs").style("gap: 0.4rem"):
        ui.spinner(size="1.1rem")
        ui.label(label).classes("text-sm font-bold")
        ticker = ui.label(_clock(elapsed)).classes("text-xs font-mono")
    ui.label(description).classes("text-xs opacity-70")
    return ticker


def _clock(seconds: float) -> str:
    minutes, rest = divmod(int(seconds), 60)
    return f"{minutes}:{rest:02d}"


def can_type(player: PlayerView, phase: Role | None) -> bool:
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
