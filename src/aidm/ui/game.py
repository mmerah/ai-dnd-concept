import logging
from asyncio import get_running_loop
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from time import monotonic

from nicegui import ui

from aidm.app.runtime import BEGUN, CROSSED, GameService, Runtime
from aidm.core.facts import DiceEvent, Fact, cards
from aidm.core.play import Answer, Speaker
from aidm.core.views import speaker_of
from aidm.turn.run import TurnStep

from .panels import NO_WAY_ON, journal_panel, scene_sidebar
from .widgets import (
    avatar,
    decision_widget,
    page_header,
    working,
)

_SCENE_HEIGHT = "calc(25vh - 1rem)"

_ART_BOX = f"flex: none; height: {_SCENE_HEIGHT}; max-width: 50%; aspect-ratio: 16 / 9"

_STEP_COPY: dict[TurnStep, tuple[str, str]] = {
    "master": (
        "Game Master",
        "Works out what your action actually does: who reacts, what changes, "
        "and whether the dice decide it.",
    ),
    "narrator": ("Narrator", "Writes what you see and hear this turn."),
    "worldsmith": (
        "Worldsmith",
        "Writes the next scene or region: where the story goes and who is waiting there. "
        "This one is slow — a few minutes is normal.",
    ),
}

LOGGER = logging.getLogger(__name__)


@dataclass
class GameView:
    runtime: Runtime
    session: GameService
    shown_art: tuple[Path | None, bool] = (None, False)
    shown_clip: tuple[Path | None, bool] = (None, False)
    autoplay_clip: Path | None = None
    # Both are built by the page below this view, and the panels reach them through it.
    composer: ui.input | None = None
    transcript: ui.scroll_area | None = None
    # What the last poll read: the phase, the facts landed, the exchanges filed.
    seen: tuple[TurnStep | None, int, int] = (None, 0, 0)
    step_started: float | None = None
    ticker: ui.label | None = None


def refresh_all() -> None:
    for panel in (
        scene_header,
        chat,
        live_turn,
        decision_panel,
        way_on_panel,
        scene_sidebar,
        journal_panel,
    ):
        panel.refresh()


@ui.refreshable
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
            ui.label(scene.situation).classes("text-sm opacity-70")


@ui.refreshable
def chat(view: GameView) -> None:
    session = view.session
    history = session.engine.history(session.state)
    if not history:
        ui.label(session.state.scenario.premise).classes("text-sm italic opacity-70")
    # The live decision widget sits directly below the last exchange, so it needs no pause line.
    last = history[-1] if history and session.state.pending is not None else None
    player = speaker_of(session.player_view().player)
    heading = ""
    for exchange in history:
        if exchange.where and exchange.where != heading:
            heading = exchange.where
            ui.label(heading).classes("w-full text-center text-xs uppercase opacity-50 q-mt-md")
        if exchange.prompt in (BEGUN, CROSSED):
            # A turn nobody played: the story's own marker, never the player's words.
            ui.label(exchange.prompt).classes("w-full text-center text-xs italic opacity-60")
        else:
            _bubble(session, player, exchange.prompt, sent=True)
        for fact in exchange.facts:
            _card(fact)
        for line in exchange.lines:
            _bubble(session, line.speaker, line.text, sent=False)
        if exchange.decision and exchange is not last:
            ui.label(f"Paused: {exchange.decision}").classes("text-xs italic opacity-60")
    # The newest clip only: every `ui.audio` registers a route, and a refresh rebuilds them all.
    if history and session.reader is not None and (clip := session.reader.clip(history[-1])):
        ui.audio(clip, autoplay=clip == view.autoplay_clip)
        # Consumed by this render: a later refresh of the same turn must not restart it.
        view.autoplay_clip = None


@ui.refreshable
def live_turn(view: GameView) -> None:
    session = view.session
    turn = session.turn
    if turn is not None:
        _bubble(session, speaker_of(session.player_view().player), turn.prompt, sent=True)
        shown = cards(turn.facts)
        for fact in shown:
            _card(fact, live=fact is shown[-1])
    elif session.intent:
        _bubble(session, speaker_of(session.player_view().player), session.intent, sent=True)
    view.ticker = None
    if session.phase is not None:
        elapsed = 0.0 if view.step_started is None else monotonic() - view.step_started
        view.ticker = _inline_status(session.phase, elapsed)


def poll_turn(view: GameView) -> None:
    """The page reads the turn once a second; the turn never calls the page."""
    now = _observed(view.session)
    if now[0] != view.seen[0]:
        view.step_started = None if now[0] is None else monotonic()
    if now != view.seen:
        view.seen = now
        if view.composer is not None:
            view.composer.props(f'placeholder="{_composer_placeholder(view)}"')
        refresh_all()
        _scroll(view)
    ticker, started = view.ticker, view.step_started
    if ticker is not None and started is not None and not ticker.is_deleted:
        ticker.set_text(_clock(monotonic() - started))


def poll_media(view: GameView) -> None:
    """The illustration and the clip are both generated after the turn commits and watched for."""
    session = view.session
    shown = (session.scene_art(), session.scene_pending())
    if shown != view.shown_art:
        view.shown_art = shown
        scene_header.refresh()
    clip = (session.newest_clip(), session.clip_pending())
    if clip != view.shown_clip:
        view.shown_clip = clip
        if clip[0] is not None:
            view.autoplay_clip = clip[0]
        chat.refresh()


def refuse_play(view: GameView) -> bool:
    refusal = view.runtime.play_refusal(view.session)
    if refusal is None:
        return False
    ui.notify(refusal, type="warning")
    return True


async def submit(view: GameView, box: ui.input, moving_on: bool = False) -> None:
    session = view.session
    typed = (box.value or "").strip()
    LOGGER.info("player submitted prompt: non_empty=%s busy=%s", bool(typed), session.busy)
    if not typed or refuse_play(view):
        return
    box.value = ""
    # Quasar never saw the typed value change, so only an explicit push empties the composer.
    _ = box.run_method("updateValue")
    typed_input = typed if session.player_view().prompt is None else Answer(text=typed)
    await _send(view, typed_input, moving_on=moving_on)


async def move_on(view: GameView, intent: str) -> None:
    if refuse_play(view):
        return
    pending = view.session.player_view().prompt
    if pending is not None and not pending.allows_text:
        ui.notify("Choose an option above.", type="warning")
        return
    await _send(view, intent if pending is None else Answer(text=intent), moving_on=True)


@ui.refreshable
def way_on_panel(view: GameView) -> None:
    """The banner, not the offer: legible after a reload, once the asking has scrolled away."""
    if not view.session.transition_available():
        return
    with (
        ui.row().classes("game-card game-decision w-full items-center no-wrap").style("gap: 0.4rem")
    ):
        ui.icon("arrow_forward").classes("game-card-icon")
        ui.label("there is more beyond here").classes("text-xs font-bold game-outcome")
        ui.label("keep playing, or say what you pursue and press Move on").classes(
            "text-xs opacity-60"
        )


@ui.refreshable
def decision_panel(view: GameView) -> None:
    pending = view.session.player_view().prompt
    if pending is None:
        return

    async def answer(option_id: str) -> None:
        if refuse_play(view):
            return
        await _send(view, Answer(option_id=option_id))

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
        # `phase` is only the source NiceGUI needs: it re-runs every backward on its 0.1s poll.
        ui.label("").classes("text-xs self-center").style(
            "color: var(--game-danger)"
        ).bind_text_from(session, "phase", backward=lambda _: session.player_view().over or "")
        box = (
            ui.input(placeholder=_composer_placeholder(view))
            .classes("flex-grow")
            .props("outlined autogrow type=textarea borderless")
            .bind_enabled_from(session, "phase", backward=partial(_can_type, session))
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
            .bind_enabled_from(session, "phase", backward=partial(_can_type, session))
        )
        _ = (
            ui.button("Move on", icon="arrow_forward", on_click=lambda: submit(view, box, True))
            .props("no-caps outline dense")
            .bind_enabled_from(session, "phase", backward=partial(_can_type, session))
            .bind_visibility_from(
                session, "phase", backward=lambda _: session.transition_available()
            )
        )
    view.composer = box


async def restart(view: GameView) -> None:
    session = view.session
    if refuse_play(view):
        return
    session.restart()
    view.seen = _observed(session)
    refresh_all()
    await _open(view)


def game_page(runtime: Runtime, session: GameService) -> None:
    view = GameView(runtime, session)
    if session.unopened():
        ui.timer(0.1, lambda: _open(view), once=True)
    else:
        session.illustrate()
    with page_header(session.state.scenario.title, session.engine.title):
        ui.space()
        ui.button("restart", on_click=lambda: restart(view)).props("flat color=white dense")

    # Account for the header and page padding so the input stays above the fold.
    with ui.splitter(value=55).classes("w-full").style("height: calc(100vh - 6rem)") as splitter:
        with splitter.before, ui.column().classes("w-full h-full p-4").style("gap: 0.5rem"):
            scene_header(session)
            with ui.scroll_area().classes("w-full flex-grow game-transcript") as transcript:
                chat(view)
                live_turn(view)
            decision_panel(view)
            way_on_panel(view)
            composer(view)
            view.transcript = transcript
            ui.timer(0.5, lambda: transcript.scroll_to(percent=1.0), once=True)
        with splitter.after, ui.column().classes("w-full h-full").style("gap: 0"):
            with ui.tabs().classes("w-full") as tabs:
                scene_tab = ui.tab("scene")
                journal_tab = ui.tab("journal")
            with ui.tab_panels(tabs, value=scene_tab).classes("w-full flex-grow"):
                with ui.tab_panel(scene_tab), ui.scroll_area().classes("w-full h-full"):
                    scene_sidebar(session, partial(move_on, view))
                with ui.tab_panel(journal_tab), ui.scroll_area().classes("w-full h-full"):
                    journal_panel(session)

    # A cached clip never autoplays on a page load, only one landing after.
    view.shown_clip = (session.newest_clip(), session.clip_pending())
    view.seen = _observed(session)

    ui.timer(1.0, lambda: poll_turn(view))
    if session.media is not None or session.reader is not None:
        ui.timer(3.0, lambda: poll_media(view))


def _scene_art(session: GameService) -> None:
    art = session.scene_art()
    if art is not None:
        # `contain` letterboxes a frame drawn at another ratio instead of cropping its subject.
        ui.image(art).props("fit=contain").classes("rounded-borders").style(_ART_BOX)
    elif session.scene_pending():
        ui.skeleton().classes("rounded-borders").style(_ART_BOX)


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


def _composer_placeholder(view: GameView) -> str:
    phase = view.session.phase
    if phase is not None:
        return f"{_STEP_COPY[phase][0]} is working..."
    pending = view.session.player_view().prompt
    if pending is not None:
        if not pending.allows_text:
            return "Choose an option above."
        return "The game is waiting on your answer."
    return "What do you do?"


def _observed(session: GameService) -> tuple[TurnStep | None, int, int]:
    """The phase, the facts landed, the exchanges filed: what a render depends on."""
    turn = session.turn
    return (
        session.phase,
        0 if turn is None else len(turn.facts),
        len(session.engine.history(session.state)),
    )


def _scroll(view: GameView) -> None:
    if (transcript := view.transcript) is not None:
        # A method call on an existing element needs no NiceGUI slot; `ui.timer` here would.
        get_running_loop().call_later(0.1, lambda: transcript.scroll_to(percent=1.0))


async def _run(view: GameView, playing: Callable[[], Awaitable[None]]) -> None:
    async with working():
        await playing()
    if view.session.write_failure:
        ui.notify(NO_WAY_ON, type="warning")
    poll_turn(view)


async def _open(view: GameView) -> None:
    # A second tab's timer must not run the page reset over an opening already in flight.
    if not view.session.unopened():
        return
    await _run(view, view.session.open)


async def _send(view: GameView, player_input: str | Answer, *, moving_on: bool = False) -> None:
    session = view.session
    await _run(view, lambda: session.play(player_input, moving_on=moving_on))


def _can_type(session: GameService, phase: TurnStep | None) -> bool:
    player = session.player_view()
    typed = player.prompt is None or player.prompt.allows_text
    return phase is None and typed and player.over is None
