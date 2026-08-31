import logging
from asyncio import AbstractEventLoop, get_running_loop
from collections.abc import Sequence
from functools import partial
from pathlib import Path
from time import monotonic

from nicegui import ui

from aidm.app.runtime import GameService
from aidm.kernel.views import speaker_of
from aidm.state.entities import EntityId
from aidm.state.facts import DiceEvent, Fact
from aidm.state.play import Answer, Speaker
from aidm.turn.run import TurnStep

from .panels import journal_panel, sheet_panel
from .widgets import (
    avatar,
    decision_widget,
    page_header,
    refuse_if_busy,
    working,
)

_SCENE_HEIGHT = "calc(25vh - 1rem)"


_ART_BOX = f"flex: none; height: {_SCENE_HEIGHT}; max-width: 50%; aspect-ratio: 16 / 9"


def scene_header(session: GameService) -> None:
    scene = session.scene()
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
            _breadcrumb(session)
            ui.label(scene.situation).classes("text-sm opacity-70")


def _breadcrumb(session: GameService) -> None:
    """Where this scene sits in the story: the number of every scene played, this one marked."""
    played = session.view().player.scenes
    with ui.row().classes("items-center").style("gap: 0.3rem"):
        for number, title in enumerate(played, start=1):
            here = number == len(played)
            ui.label(str(number)).classes(
                f"text-xs {'font-bold game-outcome' if here else 'opacity-40'}"
            ).tooltip(title)


def _scene_art(session: GameService) -> None:
    art = session.scene_art()
    if art is not None:
        # `contain` letterboxes a frame drawn at another ratio instead of cropping its subject.
        ui.image(art).props("fit=contain").classes("rounded-borders").style(_ART_BOX)
    elif session.scene_pending():
        ui.skeleton().classes("rounded-borders").style(_ART_BOX)


def chat(session: GameService) -> None:
    if not session.state.history:
        ui.label(session.state.scenario.premise).classes("text-sm italic opacity-70")
    here = ""
    history = session.state.history
    last = history[-1] if history and session.state.pending is not None else None
    player = speaker_of(session.view().player.player)
    for exchange in history:
        if exchange.scene != here:
            here = exchange.scene
            ui.label(here).classes("w-full text-center text-xs uppercase opacity-50 q-mt-md")
        _bubble(session, player, exchange.prompt, sent=True)
        for fact in exchange.facts:
            _card(fact)
        for line in exchange.lines:
            _bubble(session, line.speaker, line.text, sent=False)
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


def _bubble(session: GameService, speaker: Speaker | None, text: str, *, sent: bool) -> None:
    icon = None if speaker is None else session.icon(EntityId(speaker.id))
    name = "DM" if speaker is None else speaker.name
    message = ui.chat_message(text, name=name, sent=sent).classes("w-full")
    if speaker is None:
        message.props("bg-color=grey-3")
    with message.add_slot("avatar"):
        avatar(icon, None if speaker is None else name)


_STEP_COPY: dict[TurnStep, tuple[str, str]] = {
    "master": (
        "Game Master",
        "Works out what your action actually does: who reacts, what changes, "
        "and whether the dice decide it.",
    ),
    "narrator": ("Narrator", "Writes what you see and hear this turn."),
    "worldsmith": (
        "Worldsmith",
        "Writes the next scene: where the story goes and who is waiting there. "
        "This one is slow — a few minutes is normal.",
    ),
}


def live_turn(
    session: GameService, prompt: str | None, facts: Sequence[Fact], elapsed: float
) -> ui.label | None:
    if prompt is not None:
        _bubble(session, speaker_of(session.view().player.player), prompt, sent=True)
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
    def __init__(self, session: GameService) -> None:
        self.session = session
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

    def log(self, line: str) -> None:
        if self.agent_log is not None and not self.agent_log.is_deleted:
            self.agent_log.push(line)

    @ui.refreshable_method
    def scene(self) -> None:
        scene_header(self.session)

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
    def way_on(self) -> None:
        way_on_panel(self)

    @ui.refreshable_method
    def sheet(self) -> None:
        sheet_panel(self.session)

    @ui.refreshable_method
    def journal(self) -> None:
        journal_panel(self.session)

    def refresh_all(self) -> None:
        for panel in (
            self.scene,
            self.chat,
            self.live_turn,
            self.decision,
            self.way_on,
            self.sheet,
            self.journal,
        ):
            panel.refresh()


def _composer_placeholder(view: GameView) -> str:
    step = view.session.step
    if step is not None:
        return f"{_STEP_COPY[step][0]} is working..."
    pending = view.session.view().player.prompt
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


async def _send(
    view: GameView, player_input: str | Answer, bubble: str, *, moving_on: bool = False
) -> None:
    session = view.session
    view.live_prompt, view.live_facts = bubble, []
    view.live_turn.refresh()
    _scroll(view)
    async with working(session):
        loop = get_running_loop()
        await session.play(
            player_input,
            on_step=lambda step: on_step(view, step),
            on_fact=lambda fact: on_fact(view, fact, loop),
            moving_on=moving_on,
        )
    view.log(session.master_log)
    session.step = None
    view.live_prompt, view.live_facts, view.step_started = None, [], None
    if view.composer is not None:
        view.composer.props(f'placeholder="{_composer_placeholder(view)}"')
    view.refresh_all()
    _scroll(view)


async def submit(view: GameView, box: ui.input, moving_on: bool = False) -> None:
    session = view.session
    typed = (box.value or "").strip()
    LOGGER.info("player submitted prompt: non_empty=%s busy=%s", bool(typed), session.busy)
    if not typed or refuse_if_busy(session):
        return
    box.value = ""
    # Quasar never saw the typed value change, so only an explicit push empties the composer.
    _ = box.run_method("updateValue")
    typed_input = typed if session.view().player.prompt is None else Answer(text=typed)
    await _send(view, typed_input, typed, moving_on=moving_on)


def way_on_panel(view: GameView) -> None:
    """The banner, not the offer: the Move on button beside the composer is the offer. This keeps
    the state legible after a reload, when the narrator's asking has scrolled away."""
    if not view.session.view().player.settled:
        return
    with (
        ui.row().classes("game-card game-decision w-full items-center no-wrap").style("gap: 0.4rem")
    ):
        ui.icon("arrow_forward").classes("game-card-icon")
        ui.label("this scene is settled").classes("text-xs font-bold game-outcome")
        ui.label("keep playing, or say where you go and press Move on").classes(
            "text-xs opacity-60"
        )


def _can_type(session: GameService, busy: bool) -> bool:
    player = session.view().player
    typed = player.prompt is None or player.prompt.allows_text
    return not busy and typed and player.over is None


def decision_panel(view: GameView) -> None:
    pending = view.session.view().player.prompt
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
        decision_widget(pending.prompt, pending.options, answer)
        if pending.allows_text:
            pointer = "Or answer" if pending.options else "Answer"
            ui.label(f"{pointer} in your own words below.").classes("text-xs opacity-60")


def composer(view: GameView) -> None:
    session = view.session
    with ui.row().classes("w-full no-wrap items-end game-composer q-pa-sm").style("gap: 0.5rem"):
        # `busy` is only the source NiceGUI needs: it re-runs every backward on its 0.1s poll.
        ui.label("").classes("text-xs self-center").style(
            "color: var(--game-danger)"
        ).bind_text_from(session, "busy", backward=lambda _: session.view().player.over or "")
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
        _ = (
            ui.button("Move on", icon="arrow_forward", on_click=lambda: submit(view, box, True))
            .props("no-caps outline dense")
            .bind_enabled_from(session, "busy", backward=partial(_can_type, session))
            .bind_visibility_from(session, "busy", backward=lambda _: session.view().player.settled)
        )
    view.composer = box


def restart(view: GameView) -> None:
    session = view.session
    if refuse_if_busy(session):
        return
    session.restart()
    view.live_prompt, view.live_facts = None, []
    view.refresh_all()


def game_page(session: GameService) -> None:
    session.illustrate_scene()
    view = GameView(session)
    with page_header(session.state.scenario.title, session.engine.title):
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
            view.way_on()
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
                    with ui.expansion("game master", value=True).classes("w-full"):
                        view.agent_log = ui.log(max_lines=500).classes("w-full h-64 text-xs")

    ui.timer(1.0, lambda: tick_elapsed(view))
    if session.media is not None:
        ui.timer(3.0, lambda: poll_art(view))
