from asyncio import get_running_loop
from collections.abc import Awaitable, Callable
from functools import partial
from pathlib import Path
from time import monotonic

from nicegui import app, ui
from nicegui.events import GenericEventArguments, ScrollEventArguments

from aidm.app.runtime import Busy, GameService
from aidm.core.entities import Refusal
from aidm.core.play import Answer, Exchange
from aidm.core.views import PlayerView
from aidm.ui import transcript
from aidm.ui.widgets import (
    DiceSound,
    Speaker,
    alert,
    decision_widget,
    entity_row,
    labeled_value,
    media_url,
    media_urls,
    page_header,
    section,
    typed,
    warn,
)

TURN_FAILED = "Something went wrong. The turn did not complete. Look in the server log."

SCENE_TAB = "scene"
JOURNAL_TAB = "journal"
# Not the header's `menu_book`: two buttons with one icon make every icon locator ambiguous.
RAIL: tuple[tuple[str, str, str], ...] = (
    (SCENE_TAB, "map", "Scene"),
    (JOURNAL_TAB, "history_edu", "Journal"),
)


class GamePage:
    """One page object per browser tab; several tabs can share one session."""

    def __init__(self, session: GameService) -> None:
        self.session = session
        self.shown_art: Path | None = None
        self.followed: Exchange | None = None
        self.shown_clips: tuple[Path | None, ...] = ()
        self.reading: str = ""
        self.read_buttons: dict[str, ui.button] = {}
        self.scene_open: bool = False
        self.scroll: ui.scroll_area
        self.drawer: ui.right_drawer
        self.tabs: ui.tabs
        self.rail: dict[str, ui.button] = {}
        self.dice: DiceSound
        self.speaker: Speaker
        self.sound: ui.button
        self.stop_button: ui.button
        self.new_activity: ui.button
        self.scene_card: ui.element
        self.restart_dialog: ui.dialog
        self.restart_label: ui.label
        self.restart_item: ui.menu_item
        self.seen: transcript.Observed = transcript.Observed(
            working_role=None, facts=0, exchanges=0, action=None, ending=None
        )
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
            session.present(spoken=False)
        with page_header(
            session.state.scenario.title, session.engine.title, look=session.engine.look
        ):
            ui.space()
            self.stop_button = (
                ui.button(icon="stop_circle", on_click=self.stop_reading)
                .props('flat round aria-label="Stop reading"')
                .tooltip("Stop reading")
            )
            self.stop_button.set_visibility(False)
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
                # Below 600px the drawer covers the header, so it needs its own close button.
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
        self.speaker = Speaker()
        self.speaker.on("reading", self.reading_state)
        # A cached clip never plays on a page load, only a line landing after.
        self.followed, self.shown_clips = self._newest_clips()
        self.shown_art = session.scene_art()
        self.seen = transcript.Observed.of(session, self.view, self.history)
        self._set_composer()
        self._clear_spent_draft()

        ui.timer(1.0, self.poll_turn)
        if session.presenter.enabled:
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
                    ui.image(media_url(art)).props("fit=contain").classes("game-scene-art")
            ui.icon("expand_more").classes("game-scene-chevron lt-sm")

    @ui.refreshable_method
    def chat(self) -> None:
        self.read_buttons = transcript.chat(
            self.session,
            self.view,
            self.history,
            reading=self.reading,
            accept=self.accept,
            read=self.read_from,
        )

    @ui.refreshable_method
    def live_turn(self) -> None:
        elapsed = 0.0 if self.step_started is None else monotonic() - self.step_started
        self.ticker = transcript.live_turn(self.session, self.view, elapsed)

    @ui.refreshable_method
    def way_on_panel(self) -> None:
        action = self.view.action
        if action is None:
            return
        with ui.row().classes(transcript.DECISION_ROW):
            ui.icon("arrow_forward").classes("game-card-icon")
            ui.label("there is more beyond here").classes("text-xs font-bold game-outcome")
            ui.label(f"{action.brief} Type your words, then press {action.name}.").classes(
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
                enabled=self.session.working_role is None,
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
        now = transcript.Observed.of(session, self.view, self.history)
        if now.working_role != self.seen.working_role:
            self.step_started = None if now.working_role is None else monotonic()
        if now != self.seen:
            if self._dice_landed(now):
                self.dice.play()
            closed = now.exchanges > self.seen.exchanges
            # Both reads are of the old `seen`, so neither may move below this line.
            whole = transcript.whole_page(now, self.seen)
            self.seen = now
            if closed:
                self._clear_spent_draft()
            self.refresh(whole=whole)
            self._scroll(follow=self.at_end or self.own_move)
        self._set_composer()
        ticker, started = self.ticker, self.step_started
        if ticker is not None and started is not None and not ticker.is_deleted:
            ticker.set_text(transcript.clock(monotonic() - started))

    def _clear_spent_draft(self) -> None:
        history = self.history
        newest_prompt = history[-1].words if history else ""
        if transcript.draft_spent(typed(self.box), newest_prompt):
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
        newest, clips = self._newest_clips()
        if newest != self.followed or clips != self.shown_clips:
            self.speaker.follow(media_urls(clips), restart=newest != self.followed)
            self.followed, self.shown_clips = newest, clips
            self.chat.refresh()

    def _newest_clips(self) -> tuple[Exchange | None, tuple[Path | None, ...]]:
        history = self.session.state.exchanges()
        if not history:
            return None, ()
        return history[-1], self.session.clips(history[-1])

    def read_from(self, exchange: Exchange, index: int) -> None:
        urls = media_urls(self.session.clips(exchange))
        if urls[index] == self.reading:
            self.speaker.stop()
        else:
            self.speaker.play_from(urls, index)

    def stop_reading(self) -> None:
        self.speaker.stop()

    def reading_state(self, event: GenericEventArguments) -> None:
        self.reading = str(event.args)
        self.stop_button.set_visibility(bool(self.reading))
        for url, button in self.read_buttons.items():
            if not button.is_deleted:
                reading = url == self.reading
                button.set_icon(transcript.READ_ICONS[reading])

    async def play(self, answer: Answer) -> bool:
        self.own_move = True
        return await self._run(lambda: self.session.play(answer))

    async def answered(self, option_id: str) -> None:
        await self.play(Answer(option_id=option_id))

    async def accept(self, proposal: str) -> None:
        await self.play(Answer(text=proposal))

    async def submit(self) -> None:
        words = typed(self.box)
        if not words:
            return
        self.own_move = True
        if await self._run(lambda: self.session.play(Answer(text=words))):
            self._clear_box()

    async def act(self) -> None:
        action = self.view.action
        if action is None:
            warn("The way on has changed.")
            return
        words = typed(self.box)
        self.own_move = True
        if await self._run(lambda: self.session.act(action.id, words)):
            self._clear_box()

    async def restart(self) -> None:
        # A menu action, not a composer double-click: any refusal here must reach the player.
        try:
            await self.session.restart()
        except Refusal as error:
            alert(str(error))
            return
        # The new opening is read even when it repeats the old one word for word.
        self.followed, self.shown_clips = None, ()
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
        self.at_end = transcript.near_end(
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
        admitted = session.gate.admitted
        free = admitted is None or admitted is session
        typing = free and transcript.can_type(player, session.working_role)
        self.box.set_enabled(typing)
        self.send.set_enabled(typing)
        action = player.action
        self.action_button.set_enabled(typing)
        self.action_button.set_visibility(action is not None)
        self.action_button.set_text("" if action is None else action.name)
        self.over_label.set_text(player.ending or "")
        self.box.props(f'placeholder="{transcript.placeholder(player, session.working_role)}"')
        self.restart_item.set_enabled(session.working_role is None)

    def _dice_landed(self, now: transcript.Observed) -> bool:
        since = self.seen.facts
        closed = False
        if now.exchanges > self.seen.exchanges:
            closed = transcript.rolled_since(self.history[-1].facts, since)
            since = 0
        turn = self.session.turn
        return closed or (turn is not None and transcript.rolled_since(turn.facts, since))

    def _scroll(self, *, follow: bool) -> None:
        if not follow:
            self.new_activity.set_visibility(True)
            return
        self.new_activity.set_visibility(False)
        # A method call on an existing element needs no NiceGUI slot; `ui.timer` here would.
        get_running_loop().call_later(0.1, lambda: self.scroll.scroll_to(percent=1.0))

    async def _opened(self, opener: ui.timer) -> None:
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
            if blocked:
                opener.interval = 1.0
            else:
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
            if not self.box.is_deleted:
                self.poll_turn()
            # A move that changed nothing must not pull a reader down on the next change.
            self.own_move = False
        return True


def game_page(session: GameService) -> None:
    if ui.context.client.is_deleted:
        return
    GamePage(session).build()
