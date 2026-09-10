import logging
from asyncio import get_running_loop
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from time import monotonic
from typing import Self

from nicegui import app, ui
from nicegui.events import GenericEventArguments, ScrollEventArguments

from aidm.app.runtime import MARKS, GameService, Runtime
from aidm.config import Role
from aidm.core.entities import EntityId, Refusal
from aidm.core.facts import DiceEvent, Fact, cards
from aidm.core.play import Answer, DecisionOption, Exchange
from aidm.core.views import PlayerView
from aidm.ui.dice import DiceTray, rolled_since
from aidm.ui.dictation import Dictation
from aidm.ui.widgets import (
    avatar,
    decision_widget,
    entity_row,
    heading,
    labeled_value,
    page_header,
    section,
)

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

_DICTATION_FAILURES = {
    "not-allowed": "The browser refused the microphone (a secure context is needed).",
    "audio-capture": "No microphone.",
    "no-speech": "Nothing was heard.",
}

SCENE_TAB = "scene"
JOURNAL_TAB = "journal"
# Not the header's `menu_book`: two buttons with one icon make every icon locator ambiguous.
RAIL: tuple[tuple[str, str, str], ...] = (
    (SCENE_TAB, "map", "Scene"),
    (JOURNAL_TAB, "history_edu", "Journal"),
)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Observed:
    phase: Role | None
    facts: int
    exchanges: int
    action: DecisionOption | None
    over: str | None

    @classmethod
    def of(cls, session: GameService, view: PlayerView, history: Sequence[Exchange]) -> Self:
        return cls(
            session.phase,
            0 if session.turn is None else len(session.turn.facts),
            len(history),
            view.action,
            view.over,
        )


class GamePage:
    """One per tab; several tabs may share one session."""

    def __init__(self, runtime: Runtime, session: GameService) -> None:
        self.runtime = runtime
        self.session = session
        self.shown_art: Path | None = None
        self.shown_clip: Path | None = None
        self.autoplay_clip: Path | None = None
        self.scene_open: bool = False
        self.transcript: ui.scroll_area
        self.drawer: ui.right_drawer
        self.tabs: ui.tabs
        self.rail: dict[str, ui.button] = {}
        self.dice: DiceTray
        self.sound: ui.button
        self.new_activity: ui.button
        self.scene_card: ui.element
        self.restart_dialog: ui.dialog
        self.restart_label: ui.label
        self.seen: Observed = Observed(None, 0, 0, None, None)
        self.view: PlayerView
        self.history: tuple[Exchange, ...]
        self.step_started: float | None = None
        self.ticker: ui.label | None = None
        self.box: ui.input
        self.send: ui.button
        self.action_button: ui.button
        self.over_label: ui.label
        self.at_end: bool = True
        self.own_move: bool = False

    def build(self) -> None:
        session = self.session
        self.view = session.player_view()
        self.history = session.history()
        if session.unopened():
            ui.timer(0.1, self._open, once=True)
        else:
            session.illustrate()
        with page_header(
            session.state.scenario.title, session.engine_title, engine=session.engine_id
        ):
            ui.space()
            self.sound = ui.button(icon="volume_up", on_click=self.toggle_sound).props("flat round")
            ui.button(icon="menu_book", on_click=lambda: self.drawer.toggle()).props("flat round")
            with ui.button(icon="more_vert").props("flat round"), ui.menu():
                ui.menu_item("Restart this game", on_click=self.confirm_restart)

        ui.query(".nicegui-content").style("padding: 0; gap: 0")
        with ui.row().classes("w-full h-full no-wrap").style("gap: 0"):
            self.nav_rail()
            with (
                ui.column()
                .classes("self-stretch flex-grow game-panel game-main")
                .style("gap: 0; min-width: 0")
            ):
                self.scene_header()
                # No padding class: NiceGUI already pads the scroll content, and twice would
                # push every bubble off the measure the scene title and composer sit on.
                with ui.scroll_area().classes("w-full flex-grow game-transcript") as transcript:
                    self.chat()
                    self.live_turn()
                self.transcript = transcript
                transcript.on_scroll(self.scrolled)
                ui.timer(0.5, lambda: transcript.scroll_to(percent=1.0), once=True)
                self.foot()

        self.drawer = ui.right_drawer(value=None).props("width=420").classes("game-drawer")
        with (
            self.drawer,
            ui.column().classes("game-panel game-drawer-panel").style("gap: 0"),
        ):
            with ui.row().classes("w-full items-center no-wrap").style("gap: 0"):
                with ui.tabs(on_change=lambda e: self.mark_rail(str(e.value))).classes(
                    "flex-grow"
                ) as self.tabs:
                    ui.tab(SCENE_TAB, label="Scene")
                    ui.tab(JOURNAL_TAB, label="Journal")
                # Below 600px the drawer covers the header, so it carries its own way out.
                ui.button(icon="close", on_click=self.drawer.hide).props("flat round").classes(
                    "lt-sm"
                )
            with ui.tab_panels(self.tabs, value=SCENE_TAB).classes("w-full flex-grow"):
                with ui.tab_panel(SCENE_TAB), ui.scroll_area().classes("w-full h-full"):
                    self.sidebar()
                with ui.tab_panel(JOURNAL_TAB), ui.scroll_area().classes("w-full h-full"):
                    self.journal()

        with ui.dialog() as self.restart_dialog, ui.card():
            self.restart_label = ui.label()
            with ui.row():
                ui.button("Keep playing", on_click=self.restart_dialog.close).props("flat")
                ui.button("Restart", on_click=self.confirmed_restart)

        self.dice = DiceTray(session.dice_look)
        self.dice.on("sound", self.sound_state)
        # A cached clip never autoplays on a page load, only one landing after.
        self.shown_clip = session.newest_clip()
        self.seen = Observed.of(session, self.view, self.history)
        self._set_composer()
        self._clear_spent_draft()

        ui.timer(1.0, self.poll_turn)
        if session.presents:
            ui.timer(3.0, self.poll_media)

    def refresh(self) -> None:
        self.scene_header.refresh()
        self.chat.refresh()
        self.live_turn.refresh()
        self.decision_panel.refresh()
        self.way_on_panel.refresh()
        self.sidebar.refresh()
        self.journal.refresh()

    def foot(self) -> None:
        """In the column, not `ui.footer`: a page-wide footer ignores the rail and the drawer."""
        with (
            ui.column().classes("w-full game-foot"),
            ui.column().classes("w-full game-measure q-px-md q-py-sm"),
        ):
            self.new_activity = ui.button(
                "New activity", icon="arrow_downward", on_click=self.catch_up
            ).props("dense")
            self.new_activity.set_visibility(False)
            self.decision_panel()
            self.way_on_panel()
            self.composer()

    def nav_rail(self) -> None:
        with ui.column().classes("game-rail h-full items-center q-pt-md").style("gap: 0.4rem"):
            for name, icon, label in RAIL:
                self.rail[name] = (
                    ui.button(label, icon=icon, on_click=partial(self.show_tab, name))
                    .props("flat")
                    .classes("game-rail-btn")
                )
        self.mark_rail(SCENE_TAB)

    def show_tab(self, name: str) -> None:
        self.tabs.set_value(name)
        self.drawer.show()

    def mark_rail(self, active: str) -> None:
        for name, button in self.rail.items():
            button.classes(add="game-rail-on" if name == active else "", remove="game-rail-on")

    def toggle_scene(self) -> None:
        """A phone shows the scene as a strip; the tap opens the whole frame."""
        self.scene_open = not self.scene_open
        self.scene_card.classes(toggle="game-scene-open")

    @ui.refreshable_method
    def scene_header(self) -> None:
        session = self.session
        art = session.scene_art()
        open_class = " game-scene-open" if self.scene_open else ""
        self.scene_card = ui.element("div").classes("game-scene" + open_class)
        self.scene_card.on("click", self.toggle_scene)
        with self.scene_card:
            if art is not None:
                ui.image(art).classes("game-scene-wash")
            with ui.row().classes("game-scene-body w-full no-wrap").style("gap: 0"):
                with ui.column().classes("game-scene-text").style("gap: 0.15rem"):
                    ui.label("current scene").classes("text-xs game-eyebrow")
                    ui.label(self.view.scene_title).classes("game-title game-scene-title")
                    ui.label(self.view.situation).classes("text-sm opacity-80 game-scene-situation")
                if art is not None:
                    # Whole frame, bled to the edges: a drawn scene puts what matters anywhere,
                    # so it is faded into the header rather than cropped to fit a band;
                    # only the phone strip crops it.
                    ui.image(art).props("fit=contain").classes("game-scene-art")
            ui.icon("expand_more").classes("game-scene-chevron lt-sm")

    @ui.refreshable_method
    def chat(self) -> None:
        session = self.session
        history = self.history
        if not history:
            ui.label(session.state.scenario.premise).classes("text-sm italic opacity-70")
        # The live decision widget sits directly below the last exchange, so it needs no pause line.
        last = history[-1] if history and session.state.pending is not None else None
        player = self.view.player
        for exchange in history:
            if exchange.prompt in MARKS:
                ui.label(exchange.prompt).classes("w-full text-center text-xs italic opacity-60")
            else:
                _bubble(session, player.id, player.label, exchange.prompt, sent=True)
            for fact in cards(exchange.facts):
                _card(fact)
            for line in exchange.lines:
                _bubble(session, line.speaker_id, line.speaker, line.text, sent=False)
            if exchange.decision and exchange is not last:
                ui.label(f"Paused: {exchange.decision}").classes("text-xs italic opacity-60")
        if (proposed := standing_proposal(history, self.view, session.phase)) is not None:

            async def accept() -> None:
                if self.refuse_play():
                    return
                self.own_move = True
                await self._run(lambda: self.session.play(Answer(text=proposed.proposal)))

            with (
                ui.row()
                .classes("game-card game-decision w-full items-center no-wrap")
                .style("gap: 0.4rem")
            ):
                ui.icon("record_voice_over").classes("game-card-icon")
                ui.label(f"{proposed.lines[0].speaker} proposes: {proposed.proposal}").classes(
                    "text-sm"
                )
                ui.button("Accept", on_click=accept).props("outline dense")
        # The newest clip only: every `ui.audio` registers a route, and a refresh rebuilds them all.
        if clip := session.newest_clip():
            ui.audio(clip, autoplay=clip == self.autoplay_clip)
            # Consumed by this render: a later refresh of the same turn must not restart it.
            self.autoplay_clip = None

    @ui.refreshable_method
    def live_turn(self) -> None:
        session = self.session
        turn = session.turn
        player = self.view.player
        if turn is not None:
            _bubble(session, player.id, player.label, turn.prompt, sent=True)
            shown = cards(turn.facts)
            for fact in shown:
                _card(fact, live=fact is shown[-1])
        elif session.intent:
            _bubble(session, player.id, player.label, session.intent, sent=True)
        self.ticker = None
        if session.phase is not None:
            elapsed = 0.0 if self.step_started is None else monotonic() - self.step_started
            self.ticker = _inline_status(session.phase, elapsed)

    @ui.refreshable_method
    def way_on_panel(self) -> None:
        """The banner: legible after a reload, once the asking has scrolled away."""
        action = self.view.action
        if action is None:
            return
        with (
            ui.row()
            .classes("game-card game-decision w-full items-center no-wrap")
            .style("gap: 0.4rem")
        ):
            ui.icon("arrow_forward").classes("game-card-icon")
            ui.label("there is more beyond here").classes("text-xs font-bold game-outcome")
            ui.label(f"{action.detail} Press {action.label} with your words.").classes(
                "text-xs opacity-60"
            )

    @ui.refreshable_method
    def decision_panel(self) -> None:
        pending = self.view.prompt
        if pending is None:
            return

        async def answer(option_id: str) -> None:
            if self.refuse_play():
                return
            self.own_move = True
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
        view = self.view
        player = view.player
        with ui.column().classes("w-full").style("gap: 0.75rem"):
            for index, panel in enumerate(view.panels):
                # The sheet leads in both engine families, so it carries the portrait: one card
                # for one character, rather than a name and a brief said twice down the drawer.
                sheet = index == 0
                with section(panel.title, classes="game-portrait" if sheet else ""):
                    if sheet:
                        entity_row(session.icon(player.id), player.label, player.detail)
                    if not panel.rows:
                        ui.label("nothing").classes("text-sm opacity-60")
                    for row in panel.rows:
                        if row.icon_id is not None:
                            entity_row(session.icon(row.icon_id), row.label, row.detail)
                        elif row.detail:
                            labeled_value(row.label, row.detail)
                        else:
                            ui.label(row.label).classes("text-sm")

    @ui.refreshable_method
    def journal(self) -> None:
        heading("Chronicle")
        played = self.history
        for number, exchange in reversed(list(enumerate(played, start=1))):
            with ui.expansion(f"turn {number}: {exchange.prompt}").classes("w-full game-card"):
                # A speaker is named, because a bare quote reads as narration without bubbles.
                for line in exchange.lines:
                    if line.speaker_id is None:
                        ui.label(line.text).classes("whitespace-pre-wrap text-sm")
                    else:
                        with ui.row().classes("items-start no-wrap").style("gap: 0.3rem"):
                            ui.label(f"{line.speaker}:").classes(
                                "font-bold whitespace-nowrap text-sm"
                            )
                            ui.label(line.text).classes("whitespace-pre-wrap text-sm")

    def composer(self) -> None:
        with (
            ui.row().classes("w-full no-wrap items-end game-composer q-pa-sm").style("gap: 0.5rem")
        ):
            self.over_label = (
                ui.label("").classes("text-xs self-center").style("color: var(--game-danger)")
            )
            self.box = (
                ui.input()
                .classes("flex-grow")
                .props('autogrow type=textarea borderless input-style="max-height: 9rem"')
            )
            self.box.bind_value(app.storage.tab, f"draft:{self.session.slug}")
            # Enter sends on a fine pointer only; a touch keyboard's Enter must stay a newline.
            self.box.on(
                "keydown.enter",
                self.submit,
                js_handler=(
                    '(e) => { if (e.shiftKey || !matchMedia("(pointer: fine)").matches) return; '
                    "e.preventDefault(); emit(); }"
                ),
            )
            Dictation(self.box).on("dictated", self.dictated).on("failed", self.dictation_failed)
            # `color=None`: Quasar's `text-primary` would paint the glyph the button's own gold.
            self.send = (
                ui.button(icon="send", on_click=self.submit, color=None)
                .props("round flat size=lg aria-label=Send")
                .classes("game-send")
            )
            self.action_button = ui.button(
                icon="arrow_forward", on_click=lambda: self.submit(acting=True)
            ).props("outline dense")

    def poll_turn(self) -> None:
        session = self.session
        self.view, self.history = session.player_view(), session.history()
        now = Observed.of(session, self.view, self.history)
        if now.phase != self.seen.phase:
            self.step_started = None if now.phase is None else monotonic()
        if now != self.seen:
            self.dice.toss(self._landed(now))
            landed = now.exchanges > self.seen.exchanges
            self.seen = now
            self._set_composer()
            if landed:
                self._clear_spent_draft()
            self.refresh()
            self._scroll(self.at_end or self.own_move)
        ticker, started = self.ticker, self.step_started
        if ticker is not None and started is not None and not ticker.is_deleted:
            ticker.set_text(_clock(monotonic() - started))

    def _clear_spent_draft(self) -> None:
        history = self.history
        newest_prompt = history[-1].prompt if history else ""
        if draft_spent((self.box.value or "").strip(), newest_prompt):
            self.box.value = ""
            # Quasar never saw the value change, so only an explicit push empties the composer.
            self.box.run_method("updateValue")

    def poll_media(self) -> None:
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
        ui.notify(refusal, type="warning", position="top")
        return True

    async def submit(self, acting: bool = False) -> None:
        box = self.box
        typed = (box.value or "").strip()
        LOGGER.info("player submitted prompt: non_empty=%s busy=%s", bool(typed), self.session.busy)
        if not typed or self.refuse_play():
            return
        action = self.view.action
        if acting and action is None:
            ui.notify("The way on has changed.", type="warning", position="top")
            return
        self.own_move = True
        if acting and action is not None:
            landed = await self._run(lambda: self.session.act(action.id, typed))
        else:
            landed = await self._run(lambda: self.session.play(Answer(text=typed)))
        if landed:
            box.value = ""
            # Quasar never saw the value change, so only an explicit push empties the composer.
            box.run_method("updateValue")

    async def restart(self) -> None:
        if self.refuse_play():
            return
        self.session.restart()
        self.poll_turn()
        await self._open()

    async def confirm_restart(self) -> None:
        history = self.history
        if not history:
            await self.restart()
            return
        title = self.session.state.scenario.title
        self.restart_label.set_text(f"Restart {title}? {len(history)} turns are erased.")
        self.restart_dialog.open()

    async def confirmed_restart(self) -> None:
        self.restart_dialog.close()
        await self.restart()

    def toggle_sound(self) -> None:
        self.dice.run_method("toggleSound")

    def sound_state(self, e: GenericEventArguments) -> None:
        self.sound.set_icon("volume_up" if e.args else "volume_off")

    def scrolled(self, e: ScrollEventArguments) -> None:
        self.at_end = near_end(e.vertical_position, e.vertical_size, e.vertical_container_size)
        if self.at_end:
            self.new_activity.set_visibility(False)

    def catch_up(self) -> None:
        self.transcript.scroll_to(percent=1.0)
        self.new_activity.set_visibility(False)

    def dictated(self, e: GenericEventArguments) -> None:
        self.box.value = insert_at_caret(self.box.value or "", e.args["text"], e.args["caret"])
        self.box.run_method("updateValue")

    def dictation_failed(self, e: GenericEventArguments) -> None:
        ui.notify(_DICTATION_FAILURES.get(e.args, str(e.args)), type="warning", position="top")

    def _set_composer(self) -> None:
        session = self.session
        player = self.view
        typing = can_type(player, session.phase)
        self.box.set_enabled(typing)
        self.send.set_enabled(typing)
        action = player.action
        self.action_button.set_enabled(typing)
        self.action_button.set_visibility(action is not None)
        self.action_button.set_text("" if action is None else action.label)
        self.over_label.set_text(player.over or "")
        self.box.props(f'placeholder="{placeholder(player, session.phase)}"')

    def _landed(self, now: Observed) -> tuple[DiceEvent, ...]:
        """Since the last poll: the seen turn's tail once it closed, then the live turn's dice."""
        session = self.session
        since = self.seen.facts
        closed: tuple[DiceEvent, ...] = ()
        if now.exchanges > self.seen.exchanges:
            closed = rolled_since(self.history[-1].facts, since)
            since = 0
        live = () if session.turn is None else rolled_since(session.turn.facts, since)
        return closed + live

    def _scroll(self, follow: bool) -> None:
        if not follow:
            self.new_activity.set_visibility(True)
            return
        self.new_activity.set_visibility(False)
        # A method call on an existing element needs no NiceGUI slot; `ui.timer` here would.
        get_running_loop().call_later(0.1, lambda: self.transcript.scroll_to(percent=1.0))

    async def _run(self, playing: Callable[[], Awaitable[None]]) -> bool:
        """The composer greys at once, not at the next tick: a second Enter has nothing to hit."""
        for widget in (self.box, self.send, self.action_button):
            widget.set_enabled(False)
        try:
            await playing()
        except (OSError, Refusal) as error:
            ui.notify(
                f"{type(error).__name__}: {error}", type="negative", multi_line=True, position="top"
            )
            return False
        finally:
            self._set_composer()
            self.poll_turn()
            # A move that changed nothing must not pull a reader down on the next change.
            self.own_move = False
        return True

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
    message = ui.chat_message(text, name=chat_name, sent=sent).classes(
        "w-full game-message" + (" game-narration" if narration else "")
    )
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


def standing_proposal(
    history: Sequence[Exchange], player: PlayerView, phase: Role | None
) -> Exchange | None:
    newest = history[-1] if history else None
    if newest is None or not newest.proposal:
        return None
    return newest if can_type(player, phase) and player.prompt is None else None


def near_end(position: float, size: float, container: float, slack: float = 48) -> bool:
    return size - position - container <= slack


def draft_spent(draft: str, newest_prompt: str) -> bool:
    """The words sent for the turn that just landed."""
    return bool(draft) and draft == newest_prompt


def insert_at_caret(draft: str, text: str, caret: int) -> str:
    """A space on each side, unless the neighbour is already whitespace or the draft edge."""
    before, after = draft[:caret], draft[caret:]
    lead = "" if not before or before[-1].isspace() else " "
    trail = "" if not after or after[0].isspace() else " "
    return f"{before}{lead}{text}{trail}{after}"


def placeholder(player: PlayerView, phase: Role | None) -> str:
    if player.over is not None:
        return "The game is over. Restart it from the menu."
    if phase is not None:
        return f"{_STEP_COPY[phase][0]} is working..."
    if player.prompt is None:
        return "What do you do?"
    if player.prompt.allows_text:
        return "The game is waiting on your answer."
    return "Choose an option above."
