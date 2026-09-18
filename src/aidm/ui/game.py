import logging
import string
from asyncio import get_running_loop
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from time import monotonic
from typing import Self

from nicegui import app, ui
from nicegui.events import GenericEventArguments, ScrollEventArguments

from aidm.app.runtime import Busy, GameService
from aidm.config import Role
from aidm.core.entities import Refusal
from aidm.core.play import Answer, DecisionOption, Exchange
from aidm.core.views import PlayerView
from aidm.ui import transcript
from aidm.ui.dice import DiceSound, rolled_since
from aidm.ui.widgets import (
    alert,
    decision_widget,
    entity_row,
    labeled_value,
    media_url,
    page_header,
    section,
    warn,
)

LOGGER = logging.getLogger(__name__)

TURN_FAILED = "Something went wrong. The turn did not land — check the server log."
BLANK = string.whitespace + (
    "\xa0\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000"
    "\u200b\u200c\u200d\u2060\ufeff"
)

SCENE_TAB = "scene"
JOURNAL_TAB = "journal"
# Not the header's `menu_book`: two buttons with one icon make every icon locator ambiguous.
RAIL: tuple[tuple[str, str, str], ...] = (
    (SCENE_TAB, "map", "Scene"),
    (JOURNAL_TAB, "history_edu", "Journal"),
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Observed:
    phase: Role | None
    facts: int
    exchanges: int
    action: DecisionOption | None
    ending: str | None

    @classmethod
    def of(cls, session: GameService, view: PlayerView, history: Sequence[Exchange]) -> Self:
        return cls(
            phase=session.phase,
            facts=0 if session.turn is None else len(session.turn.facts),
            exchanges=len(history),
            action=view.action,
            ending=view.ending,
        )


class GamePage:
    """One per tab; several tabs may share one session."""

    def __init__(self, session: GameService) -> None:
        self.session = session
        self.shown_art: Path | None = None
        self.shown_clip: Path | None = None
        self.autoplay_clip: Path | None = None
        self.scene_open: bool = False
        self.scroll: ui.scroll_area
        self.drawer: ui.right_drawer
        self.tabs: ui.tabs
        self.rail: dict[str, ui.button] = {}
        self.dice: DiceSound
        self.sound: ui.button
        self.new_activity: ui.button
        self.scene_card: ui.element
        self.restart_dialog: ui.dialog
        self.restart_label: ui.label
        self.restart_item: ui.menu_item
        self.seen: Observed = Observed(phase=None, facts=0, exchanges=0, action=None, ending=None)
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
        self.view, self.history = session.player_view(), session.state.exchanges()
        if session.unopened:
            opener = ui.timer(0.1, lambda: self._opened(opener))
        else:
            session.illustrate()
        with page_header(
            session.state.scenario.title, session.engine.title, look=session.engine.look
        ):
            ui.space()
            self.sound = ui.button(icon="volume_up", on_click=self.toggle_sound).props("flat round")
            ui.button(icon="menu_book", on_click=lambda: self.drawer.toggle()).props("flat round")
            with ui.button(icon="more_vert").props("flat round"), ui.menu():
                self.restart_item = ui.menu_item("Restart this game", on_click=self.confirm_restart)

        ui.query(".nicegui-content").style("padding: 0; gap: 0")
        with ui.row().classes("w-full h-full no-wrap game-gap-0"):
            self.nav_rail()
            with (
                ui.column()
                .classes("self-stretch flex-grow game-panel game-main game-gap-0")
                .style("min-width: 0")
            ):
                self.scene_header()
                # No padding class: NiceGUI already pads the scroll content; twice would misalign.
                with ui.scroll_area().classes("w-full flex-grow game-transcript") as scroll:
                    self.chat()
                    self.live_turn()
                self.scroll = scroll
                scroll.on_scroll(self.scrolled)
                ui.timer(0.5, lambda: scroll.scroll_to(percent=1.0), once=True)
                self.foot()

        self.drawer = ui.right_drawer(value=None).props("width=420").classes("game-drawer")
        with (
            self.drawer,
            ui.column().classes("game-panel game-drawer-panel game-gap-0"),
        ):
            with ui.row().classes("w-full items-center no-wrap game-gap-0"):
                with ui.tabs(on_change=lambda event: self.mark_rail(str(event.value))).classes(
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

        self.dice = DiceSound()
        self.dice.on("sound", self.sound_state)
        # A cached clip never autoplays on a page load, only one landing after.
        self.shown_clip = session.newest_clip()
        self.shown_art = session.scene_art()
        self.seen = Observed.of(session, self.view, self.history)
        self._set_composer()
        self._clear_spent_draft()

        ui.timer(1.0, self.poll_turn)
        if session.presents:
            ui.timer(3.0, self.poll_media)

    def refresh(self, *, whole: bool) -> None:
        self.live_turn.refresh()
        self.decision_panel.refresh()
        self.way_on_panel.refresh()
        if not whole:
            return
        self.scene_header.refresh()
        self.chat.refresh()
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
        with ui.column().classes("game-rail h-full items-center q-pt-md game-gap-md"):
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
                ui.image(media_url(art)).classes("game-scene-wash")
            with ui.row().classes("game-scene-body w-full no-wrap game-gap-0"):
                with ui.column().classes("game-scene-text game-gap-3xs"):
                    ui.label("current scene").classes("text-xs game-eyebrow")
                    ui.label(self.view.scene_title).classes("game-title game-scene-title")
                    ui.label(self.view.situation).classes("text-sm opacity-80 game-scene-situation")
                if art is not None:
                    # Whole frame, faded into the header, not cropped; only the phone strip crops.
                    ui.image(media_url(art)).props("fit=contain").classes("game-scene-art")
            ui.icon("expand_more").classes("game-scene-chevron lt-sm")

    @ui.refreshable_method
    def chat(self) -> None:
        transcript.chat(
            self.session,
            self.view,
            self.history,
            autoplay_clip=self.autoplay_clip,
            accept=self.accept,
        )
        # Consumed by this render: a later refresh of the same turn must not restart the clip.
        self.autoplay_clip = None

    @ui.refreshable_method
    def live_turn(self) -> None:
        elapsed = 0.0 if self.step_started is None else monotonic() - self.step_started
        self.ticker = transcript.live_turn(self.session, self.view, elapsed)

    @ui.refreshable_method
    def way_on_panel(self) -> None:
        """The banner: legible after a reload, once the asking has scrolled away."""
        action = self.view.action
        if action is None:
            return
        with ui.row().classes(transcript.DECISION_ROW):
            ui.icon("arrow_forward").classes("game-card-icon")
            ui.label("there is more beyond here").classes("text-xs font-bold game-outcome")
            ui.label(f"{action.brief} Press {action.name} with your words.").classes(
                "text-xs opacity-60"
            )

    @ui.refreshable_method
    def decision_panel(self) -> None:
        pending = self.view.decision
        if pending is None:
            return
        with ui.column().classes("game-card game-decision w-full game-gap-lg"):
            with ui.row().classes("items-center no-wrap game-gap-md"):
                ui.icon("pause_circle").classes("game-card-icon")
                ui.label(pending.kind).classes("text-xs font-bold game-outcome")
                ui.label("the game is waiting on you").classes("text-xs opacity-60")
            decision_widget(
                pending.prompt,
                pending.options,
                self.answered,
                enabled=not self.session.busy,
            )
            if pending.allows_text:
                pointer = "Or answer" if pending.options else "Answer"
                ui.label(f"{pointer} in your own words below.").classes("text-xs opacity-60")

    @ui.refreshable_method
    def sidebar(self) -> None:
        session = self.session
        view = self.view
        player = view.player
        with ui.column().classes("w-full game-gap-xl"):
            for panel in view.panels:
                with section(panel.title, classes="game-portrait" if panel.portrait else ""):
                    if panel.portrait:
                        entity_row(session.icon(player.id), player.name, player.brief)
                    if not panel.rows:
                        ui.label("nothing").classes("text-sm opacity-60")
                    for row in panel.rows:
                        if row.icon_id is not None:
                            entity_row(session.icon(row.icon_id), row.name, row.brief)
                        elif row.brief:
                            labeled_value(row.name, row.brief)
                        else:
                            ui.label(row.name).classes("text-sm")

    @ui.refreshable_method
    def journal(self) -> None:
        transcript.journal(self.history)

    def composer(self) -> None:
        with ui.row().classes("w-full no-wrap items-end game-composer q-pa-sm game-gap-lg"):
            self.over_label = (
                ui.label("").classes("text-xs self-center").style("color: var(--game-danger)")
            )
            self.box = (
                ui.input()
                .classes("flex-grow")
                # theme.py's default w-full would fight flex-grow and squeeze the send button.
                .classes(remove="w-full")
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
            # `color=None`: Quasar's `text-primary` would paint the glyph the button's own gold.
            self.send = (
                ui.button(icon="send", on_click=self.submit, color=None)
                .props("round flat size=lg aria-label=Send")
                .classes("game-send")
            )
            self.action_button = ui.button(icon="arrow_forward", on_click=self.act).props(
                "outline dense"
            )

    def poll_turn(self) -> None:
        session = self.session
        self.view, self.history = session.player_view(), session.state.exchanges()
        now = Observed.of(session, self.view, self.history)
        if now.phase != self.seen.phase:
            self.step_started = None if now.phase is None else monotonic()
        if now != self.seen:
            if self._dice_landed(now):
                self.dice.play()
            closed = now.exchanges > self.seen.exchanges
            # Both reads are of the old `seen`, so neither may move below this line.
            whole = whole_page(now, self.seen)
            self.seen = now
            self._set_composer()
            if closed:
                self._clear_spent_draft()
            self.refresh(whole=whole)
            self._scroll(follow=self.at_end or self.own_move)
        ticker, started = self.ticker, self.step_started
        if ticker is not None and started is not None and not ticker.is_deleted:
            ticker.set_text(transcript.clock(monotonic() - started))

    def _clear_spent_draft(self) -> None:
        history = self.history
        newest_prompt = history[-1].words if history else ""
        if draft_spent((self.box.value or "").strip(BLANK), newest_prompt):
            self._clear_box()

    def _clear_box(self) -> None:
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

    async def play(self, answer: Answer) -> bool:
        self.own_move = True
        return await self._run(lambda: self.session.play(answer))

    async def answered(self, option_id: str) -> None:
        await self.play(Answer(option_id=option_id))

    async def accept(self, proposal: str) -> None:
        await self.play(Answer(text=proposal))

    async def submit(self) -> None:
        typed = (self.box.value or "").strip(BLANK)
        LOGGER.info("player submitted prompt: non_empty=%s busy=%s", bool(typed), self.session.busy)
        if not typed:
            return
        self.own_move = True
        if await self._run(lambda: self.session.play(Answer(text=typed))):
            self._clear_box()

    async def act(self) -> None:
        action = self.view.action
        if action is None:
            warn("The way on has changed.")
            return
        typed = (self.box.value or "").strip(BLANK)
        if not typed:
            return
        self.own_move = True
        if await self._run(lambda: self.session.act(action.id, typed)):
            self._clear_box()

    async def restart(self) -> None:
        # A menu action, not a composer double-click: any refusal here must reach the player.
        try:
            await self.session.restart()
        except Refusal as error:
            alert(str(error))
            return
        self.poll_turn()
        await self._run(self.session.open)

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

    def sound_state(self, event: GenericEventArguments) -> None:
        self.sound.set_icon("volume_up" if event.args else "volume_off")

    def scrolled(self, event: ScrollEventArguments) -> None:
        self.at_end = near_end(
            event.vertical_position, event.vertical_size, event.vertical_container_size
        )
        if self.at_end:
            self.new_activity.set_visibility(False)

    def catch_up(self) -> None:
        self.scroll.scroll_to(percent=1.0)
        self.new_activity.set_visibility(False)

    def _set_composer(self) -> None:
        session = self.session
        player = self.view
        typing = transcript.can_type(player, session.phase)
        self.box.set_enabled(typing)
        self.send.set_enabled(typing)
        action = player.action
        self.action_button.set_enabled(typing)
        self.action_button.set_visibility(action is not None)
        self.action_button.set_text("" if action is None else action.name)
        self.over_label.set_text(player.ending or "")
        self.box.props(f'placeholder="{placeholder(player, session.phase)}"')
        self.restart_item.set_enabled(not session.busy)

    def _dice_landed(self, now: Observed) -> bool:
        """Whether the closed turn's tail or the live turn rolled dice since the last poll."""
        since = self.seen.facts
        closed = False
        if now.exchanges > self.seen.exchanges:
            closed = rolled_since(self.history[-1].facts, since)
            since = 0
        turn = self.session.turn
        return closed or (turn is not None and rolled_since(turn.facts, since))

    def _scroll(self, *, follow: bool) -> None:
        if not follow:
            self.new_activity.set_visibility(True)
            return
        self.new_activity.set_visibility(False)
        # A method call on an existing element needs no NiceGUI slot; `ui.timer` here would.
        get_running_loop().call_later(0.1, lambda: self.scroll.scroll_to(percent=1.0))

    async def _opened(self, opener: ui.timer) -> None:
        """Retries while the gate is held at either end; anything else is persistent."""
        blocked = False

        async def opening() -> None:
            nonlocal blocked
            try:
                await self.session.open()
            except Busy:
                blocked = True

        try:
            _ = await self._run(opening)
        finally:
            # A raise must still stop the timer: NiceGUI swallows it and fires again in 0.1s.
            if not blocked:
                opener.cancel()

    async def _run(self, playing: Callable[[], Awaitable[None]]) -> bool:
        """The composer greys at once, not at the next tick: a second Enter has nothing to hit."""
        for widget in (self.box, self.send, self.action_button):
            widget.set_enabled(False)
        try:
            await playing()
        except Busy as busy:
            # Silent when it is this game's own turn: a double-click guard, not a message.
            if busy.elsewhere:
                alert(str(busy))
            return False
        except Refusal as error:
            alert(str(error))
            return False
        except Exception:
            # Announced, not handled: the re-raise is what logs the detail kept off the screen.
            alert(TURN_FAILED)
            raise
        finally:
            self._set_composer()
            self.poll_turn()
            # A move that changed nothing must not pull a reader down on the next change.
            self.own_move = False
        return True


def game_page(session: GameService) -> None:
    if ui.context.client.is_deleted:
        return
    GamePage(session).build()


def near_end(position: float, size: float, container: float, slack: float = 48) -> bool:
    return size - position - container <= slack


def draft_spent(draft: str, newest_prompt: str) -> bool:
    return bool(draft) and draft == newest_prompt


def whole_page(now: Observed, seen: Observed) -> bool:
    """False when only the fact count moved: the live turn is then the one part that can differ."""
    return replace(now, facts=0) != replace(seen, facts=0)


def placeholder(player: PlayerView, phase: Role | None) -> str:
    if player.ending is not None:
        return "The game is over. Restart it from the menu."
    if phase is not None:
        return f"{transcript.STEP_COPY[phase][0]} is working..."
    if player.decision is None:
        return "What do you do?"
    if player.decision.allows_text:
        return "The game is waiting on your answer."
    return "Choose an option above."
