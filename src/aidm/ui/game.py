import logging
from asyncio import AbstractEventLoop, get_running_loop
from collections.abc import Callable, Sequence
from functools import partial
from pathlib import Path
from time import monotonic

from nicegui import ui

from aidm.app.runtime import GameSession
from aidm.state.entities import PLAYER_ID, EntityId
from aidm.state.play import Answer, DecisionOption, DiceEvent, MechanicEvent
from aidm.turn.context import player_scene
from aidm.turn.run import TurnStep

from .panels import advancement_panel, journal_panel, sheet_panel, state_panel, trace_panel
from .widgets import DM_ICON, avatar, entity_row, heading, page_header, refuse_if_busy, working

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
                entity_row(session.icon(entity.id), entity.name, entity.brief)
            heading("Exits", tight=True)
            if not scene.exits:
                ui.label("None found yet.").classes("text-sm opacity-70")
            for way in scene.exits:
                name = scene.exit_name(way)
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
    for exchange in session.state.history:
        if exchange.place != here:
            here = exchange.place
            ui.label(here).classes("w-full text-center text-xs uppercase opacity-50 q-mt-md")
        _bubble(session, PLAYER_ID, exchange.prompt, sent=True)
        for event in exchange.events:
            _mechanic_event(event)
        for line in exchange.lines:
            _bubble(session, line.speaker_id, line.text, sent=False)
        if exchange.decision:
            ui.label(f"Paused: {exchange.decision}").classes("text-xs italic opacity-60")


def _mechanic_event(event: MechanicEvent) -> None:
    """Reads `MechanicEvent` only: no engine knowledge of Loner outcomes or 24XX thresholds."""
    with ui.row().classes("game-card w-full items-start no-wrap"):
        ui.icon(event.icon).classes("game-card-icon")
        with ui.column().classes("flex-grow").style("gap: 0.3rem"):
            ui.label(event.title).classes("text-sm font-bold")
            if event.badges:
                with ui.row().classes("items-center").style("gap: 0.35rem"):
                    for badge in event.badges:
                        text = f"{badge.label}: {badge.value}" if badge.value else badge.label
                        ui.badge(text).props("outline")
            if event.dice:
                with ui.row().classes("items-start").style("gap: 1rem"):
                    for group in event.dice:
                        _dice_group(group)
            if event.outcome:
                ui.label(event.outcome).classes("game-outcome")
            for effect in event.effects:
                ui.label(effect).classes("text-xs opacity-80")


def _dice_group(die: DiceEvent) -> None:
    with ui.column().style("gap: 0.2rem"):
        ui.label(die.label).classes("text-xs opacity-60")
        with ui.row().classes("no-wrap").style("gap: 0.3rem"):
            for face, value in zip(die.faces, die.rolled, strict=True):
                with (
                    ui.column()
                    .classes("game-die" + (" game-die-kept" if value == die.kept else ""))
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


_STEP_COPY: dict[TurnStep, tuple[str, str, str]] = {
    "director": (
        "gavel",
        "Director",
        "Works out what your action actually does: who reacts, what changes, "
        "and whether the dice decide it.",
    ),
    "narrator": (
        DM_ICON,
        "Narrator",
        "Writes what you see and hear this turn.",
    ),
    "scenario_creator": (
        "public",
        "Worldsmith",
        "Writes new places and people into the world, because it was running out of somewhere "
        "for you to go. This one is slow — a few minutes is normal.",
    ),
}


def live_turn(
    session: GameSession, prompt: str | None, events: Sequence[MechanicEvent], elapsed: float
) -> ui.label | None:
    if prompt is not None:
        _bubble(session, PLAYER_ID, prompt, sent=True)
    for event in events:
        _mechanic_event(event)
    if session.step is not None:
        return _inline_status(session.step, elapsed)
    return None


def _inline_status(step: TurnStep, elapsed: float) -> ui.label:
    _, label, description = _STEP_COPY[step]
    with ui.row().classes("items-center no-wrap q-py-xs").style("gap: 0.4rem"):
        ui.spinner(size="1.1rem")
        ui.label(label).classes("text-sm font-bold")
        ticker = ui.label(_clock(elapsed)).classes("text-xs font-mono")
    if description:
        ui.label(description).classes("text-xs opacity-70")
    return ticker


def _composer_placeholder(step: TurnStep | None) -> str:
    return "What do you do?" if step is None else f"{_STEP_COPY[step][1]} is working..."


def _clock(seconds: float) -> str:
    minutes, rest = divmod(int(seconds), 60)
    return f"{minutes}:{rest:02d}"


LOGGER = logging.getLogger(__name__)


class GameView:
    def __init__(self, session: GameSession) -> None:
        self.session = session
        self.shown_art: tuple[Path | None, bool] = (None, False)
        # Both are built by the page below this view, and the panels reach them through it.
        self.composer: ui.input | None = None
        self.transcript: ui.scroll_area | None = None
        # The turn in flight, owned by the view, never by game state; cleared on success or failure.
        self.live_prompt: str | None = None
        self.live_events: list[MechanicEvent] = []
        self.step_started: float | None = None
        self.ticker: ui.label | None = None

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
        self.ticker = live_turn(self.session, self.live_prompt, self.live_events, elapsed)

    @ui.refreshable_method
    def decision(self) -> None:
        decision_panel(self)

    @ui.refreshable_method
    def sheet(self) -> None:
        sheet_panel(self.session)

    @ui.refreshable_method
    def journal(self) -> None:
        journal_panel(self.session)

    @ui.refreshable_method
    def trace(self) -> None:
        trace_panel(self.session)

    @ui.refreshable_method
    def advancement(self) -> None:
        advancement_panel(self.session, self.refresh_all)

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
            self.advancement,
            self.state,
        ):
            panel.refresh()


def _can_type(session: GameSession, busy: bool) -> bool:
    """Bound to `session.busy`; a decision with no free text takes the composer away too."""
    pending = session.state.pending
    return not busy and (pending is None or pending.free_text)


def on_step(view: GameView, step: TurnStep) -> None:
    view.session.step = step
    view.step_started = monotonic()
    view.live_turn.refresh()
    if view.composer is not None:
        view.composer.props(f'placeholder="{_composer_placeholder(step)}"')


def on_event(view: GameView, event: MechanicEvent, loop: AbstractEventLoop) -> None:
    """Schedule refreshes on NiceGUI's loop because sync tools emit from worker threads."""
    loop.call_soon_threadsafe(_apply_event, view, event)


def _apply_event(view: GameView, event: MechanicEvent) -> None:
    view.live_events.append(event)
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
    view.live_prompt, view.live_events = bubble, []
    view.live_turn.refresh()
    _scroll(view)
    loop = get_running_loop()
    async with working(session):
        was_offered = session.advancement_offered()
        await session.submit(
            player_input,
            on_step=lambda step: on_step(view, step),
            on_event=lambda event: on_event(view, event, loop),
        )
        if not was_offered and session.advancement_offered():
            ui.notify("Something is on offer. Check the advancement tab.")
    session.step = None
    view.live_prompt, view.live_events, view.step_started = None, [], None
    if view.composer is not None:
        view.composer.props(f'placeholder="{_composer_placeholder(None)}"')
    view.refresh_all()
    _scroll(view)


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


def decision_panel(view: GameView) -> None:
    pending = view.session.state.pending
    if pending is None:
        return

    async def answer(option: DecisionOption) -> None:
        if refuse_if_busy(view.session):
            return
        await _send(view, Answer(option_id=option.id), option.label)

    with ui.column().classes("game-card w-full").style("gap: 0.5rem"):
        ui.label(pending.prompt).classes("text-sm font-bold whitespace-pre-wrap")
        with ui.row().classes("w-full items-center").style("gap: 0.5rem"):
            for option in pending.options:
                button = ui.button(option.label, on_click=partial(answer, option)).props(
                    "no-caps outline"
                )
                if option.detail:
                    button.tooltip(option.detail)


def restart(view: GameView) -> None:
    session = view.session
    if refuse_if_busy(session):
        return
    session.restart()
    view.live_prompt, view.live_events = None, []
    view.refresh_all()


def game_page(session: GameSession) -> None:
    session.illustrate_scene()
    view = GameView(session)
    with page_header(session.state.scenario.title, session.engine.badge):
        ui.space()
        ui.button("restart", on_click=lambda: restart(view)).props("flat color=white dense")

    # Account for the header and page padding so the input stays above the fold.
    with ui.splitter(value=55).classes("w-full").style("height: calc(100vh - 6rem)") as splitter:
        with splitter.before, ui.column().classes("w-full h-full p-4").style("gap: 0.5rem"):
            view.scene()
            with ui.scroll_area().classes("w-full flex-grow game-transcript") as transcript:
                view.chat()
                view.live_turn()
            view.decision()
            with (
                ui.row()
                .classes("w-full no-wrap items-end game-composer q-pa-sm")
                .style("gap: 0.5rem")
            ):
                box = (
                    ui.input(placeholder=_composer_placeholder(None))
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
            view.composer, view.transcript = box, transcript
        with splitter.after, ui.column().classes("w-full h-full").style("gap: 0"):
            advancement = session.engine.advancement
            with ui.tabs().classes("w-full") as tabs:
                scene_tab = ui.tab("scene")
                journal_tab = ui.tab("journal")
                advancement_tab = None if advancement is None else ui.tab(advancement.id)
                dev_tab = ui.tab("dev", icon="code").classes("game-dev-tab")
            with ui.tab_panels(tabs, value=scene_tab).classes("w-full flex-grow"):
                with ui.tab_panel(scene_tab), ui.scroll_area().classes("w-full h-full"):
                    view.sheet()
                with ui.tab_panel(journal_tab), ui.scroll_area().classes("w-full h-full"):
                    view.journal()
                if advancement_tab is not None:
                    with ui.tab_panel(advancement_tab), ui.scroll_area().classes("w-full h-full"):
                        view.advancement()
                with ui.tab_panel(dev_tab), ui.scroll_area().classes("w-full h-full"):
                    with ui.expansion("trace", value=True).classes("w-full"):
                        view.trace()
                    with ui.expansion("state").classes("w-full"):
                        view.state()

    ui.timer(1.0, lambda: tick_elapsed(view))
    if session.media is not None:
        ui.timer(3.0, lambda: poll_art(view))
