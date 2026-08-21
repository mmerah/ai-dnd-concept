import json
import logging
from asyncio import AbstractEventLoop, get_running_loop
from collections.abc import AsyncGenerator, Callable, Generator, Sequence
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from time import monotonic
from typing import Protocol

from nicegui import ui

from aidm.app.runtime import (
    WORLDSMITH,
    Drafted,
    GameSession,
    Offer,
    ThreadSummary,
    attributed_line,
    thread_summaries,
)
from aidm.content.io import SavedGame
from aidm.state.model import (
    PLAYER_ID,
    Applied,
    DiceEvent,
    EntityId,
    Extended,
    Fact,
    MechanicEvent,
    StepTrace,
    TraceEntry,
    Turn,
)
from aidm.turn.context import player_scene

from . import theme


class Busy(Protocol):
    busy: bool


def refuse_if_busy(session: Busy) -> bool:
    if not session.busy:
        return False
    ui.notify("Finish the current turn first.", type="warning")
    return True


@asynccontextmanager
async def working(session: Busy) -> AsyncGenerator[None]:
    """A failure is shown to the player and swallowed: the session must never stay busy."""
    session.busy = True
    try:
        yield
    except Exception as error:
        ui.notify(f"{type(error).__name__}: {error}", type="negative", multi_line=True)
    finally:
        session.busy = False


def show_engine_badge(badge: tuple[str, str]) -> None:
    label, colour = badge
    ui.badge(label).props(f"color={colour} text-color=white").classes(
        "text-sm font-bold q-px-md q-py-sm"
    )


@contextmanager
def page_header(
    title: str, badge: tuple[str, str] | None = None, home: bool = True
) -> Generator[None]:
    theme.apply()
    with ui.header().classes("items-center").style("gap: 1rem"):
        if home:
            ui.button(icon="home", on_click=lambda: ui.navigate.to("/")).props(
                "flat color=white round"
            )
        ui.label(title).classes("text-lg font-bold")
        if badge is not None:
            show_engine_badge(badge)
        yield


DM_ICON = "auto_stories"


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
            _heading("Here now", tight=True)
            if not scene.here:
                ui.label("Nobody but you.").classes("text-sm opacity-70")
            for entity in scene.here:
                _entity_row(session.icon(entity.id), entity.name, entity.brief)
            _heading("Exits", tight=True)
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


def _entity_row(icon: Path | None, name: str, sub: str) -> None:
    with ui.row().classes("w-full items-center no-wrap mt-2").style("gap: 0.5rem"):
        _avatar(icon, name)
        with ui.column().style("gap: 0"):
            ui.label(name).classes("text-sm font-bold")
            ui.label(sub).classes("text-xs opacity-70")


def chat(session: GameSession) -> None:
    if not session.state.history:
        ui.label(session.state.scenario.premise).classes("text-sm italic opacity-70")
    for exchange in session.state.history:
        _bubble(session, PLAYER_ID, exchange.prompt, sent=True)
        for event in exchange.events:
            _mechanic_event(event)
        for line in exchange.lines:
            _bubble(session, line.speaker_id, line.text, sent=False)


def _mechanic_event(event: MechanicEvent) -> None:
    """Reads `MechanicEvent` only: no engine knowledge of Loner outcomes or 24XX thresholds."""
    with ui.row().classes("game-card w-full items-start no-wrap"):
        ui.icon(event.icon).classes("game-card-icon")
        with ui.column().classes("flex-grow").style("gap: 0.3rem"):
            with ui.row().classes("items-baseline no-wrap").style("gap: 0.5rem"):
                ui.label(event.title).classes("text-sm font-bold")
                if event.subject:
                    ui.label(event.subject).classes("text-sm opacity-80")
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
        _avatar(icon, None if speaker is None else name)


def _avatar(icon: Path | None, name: str | None) -> None:
    """`name` is None for the DM, whose avatar is the one shipped material icon."""
    with ui.avatar(color="grey-8", size="42px").classes("q-mx-sm"):
        if icon is not None:
            ui.image(icon)
        elif name is None:
            ui.icon(DM_ICON)
        else:
            ui.label(name[:1].upper()).classes("text-subtitle1")


def sheet_panel(session: GameSession) -> None:
    player = session.state.player
    _entity_row(session.icon(PLAYER_ID), player.name, player.brief)
    if player.traits:
        _heading("Traits")
        with ui.row().classes("w-full items-center").style("gap: 0.35rem"):
            for trait in player.traits:
                badge = ui.badge(trait.name).props("color=grey-8 outline")
                if trait.text:
                    badge.tooltip(trait.text)
    for label, value in session.engine.sheet_view(session.state):
        _labeled_value(label, value)
    inventory = player_scene(session.state).inventory
    if inventory:
        _heading("Carrying")
        for item in inventory:
            _entity_row(session.icon(item.id), item.name, item.brief)
    threads = thread_summaries(session.state)
    if threads:
        _heading("Threads")
        for thread in threads:
            _thread_card(thread)


def _labeled_value(label: str, value: str) -> None:
    with ui.row().classes("w-full items-baseline no-wrap mt-2").style("gap: 0.5rem"):
        ui.label(label).classes("text-xs font-bold opacity-60")
        ui.label(value or "—").classes("text-sm")


def _heading(title: str, *, tight: bool = False) -> None:
    ui.label(title).classes(f"text-xs font-bold opacity-60 {'mt-2' if tight else 'mt-4'}")


def _thread_card(thread: ThreadSummary) -> None:
    with ui.column().classes("w-full mt-2").style("gap: 0"):
        ui.label(thread.title).classes("text-sm font-bold")
        parts = (thread.status, thread.stage or "", thread.clock)
        ui.label(" · ".join(part for part in parts if part)).classes("text-xs opacity-60")


def journal_panel(session: GameSession) -> None:
    threads = thread_summaries(session.state)

    def export() -> None:
        ui.notify(f"Journal written to {session.export_journal()}")

    ui.button("Export markdown", icon="download", on_click=export).props("flat dense")
    if threads:
        _heading("Threads")
        for thread in threads:
            _thread_card(thread)
    scene = player_scene(session.state)
    if scene.known_elsewhere:
        _heading("What you know of")
        for entity in scene.known_elsewhere:
            _entity_row(
                session.icon(entity.id), entity.name, scene.placement_of(entity) or entity.brief
            )
    _heading("Chronicle")
    for number, exchange in reversed(list(enumerate(session.state.history, start=1))):
        with ui.expansion(f"turn {number}: {exchange.prompt}").classes("w-full"):
            for line in exchange.lines:
                ui.markdown(attributed_line(session.state, line)).classes("text-sm")


_STEP_COPY: dict[str, tuple[str, str, str]] = {
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
    WORLDSMITH: (
        "public",
        "Worldsmith",
        "Writes new places and people into the world, because it was running out of somewhere "
        "for you to go. This one is slow — a few minutes is normal.",
    ),
}


def _step_copy(step: str) -> tuple[str, str, str]:
    return _STEP_COPY.get(step, ("bolt", step, ""))


def live_turn(session: GameSession, prompt: str | None, events: Sequence[MechanicEvent]) -> None:
    if prompt is not None:
        _bubble(session, PLAYER_ID, prompt, sent=True)
    for event in events:
        _mechanic_event(event)
    if session.step is not None:
        _inline_status(session.step)


def _inline_status(step: str) -> None:
    _, label, description = _step_copy(step)
    with ui.row().classes("items-center no-wrap q-py-xs").style("gap: 0.4rem"):
        ui.spinner(size="1.1rem")
        ui.label(label).classes("text-sm font-bold")
        _elapsed()
    if description:
        ui.label(description).classes("text-xs opacity-70")


def _composer_placeholder(step: str | None) -> str:
    return "What do you do?" if step is None else f"{_step_copy(step)[1]} is working..."


def _elapsed() -> None:
    """The timer is a child of the refreshable that draws the chip, so a repaint deletes it rather
    than leaving it ticking alongside its replacement."""
    started = monotonic()
    ticker = ui.label("0:00").classes("text-xs font-mono")
    ui.timer(1.0, lambda: ticker.set_text(_clock(monotonic() - started)))


def _clock(seconds: float) -> str:
    minutes, rest = divmod(int(seconds), 60)
    return f"{minutes}:{rest:02d}"


def trace_panel(session: GameSession) -> None:
    entries = session.entries
    if not entries:
        ui.label("No turns yet this session.").classes("opacity-60")
    turns = 0
    titles: list[str] = []
    for entry in entries:
        match entry:
            case Turn(prompt=prompt):
                turns += 1
                titles.append(f"turn {turns}: {prompt}")
            case Applied():
                titles.append(f"after turn {turns}: advancement")
            case Extended():
                titles.append(f"after turn {turns}: the world grew")
    for index, entry in reversed(list(enumerate(entries))):
        with ui.expansion(titles[index], value=index == len(entries) - 1):
            _entry_trace(entry)


def _section(title: str, body: str) -> None:
    ui.label(title).classes("text-xs font-bold opacity-60 mt-3")
    ui.label(body).classes("text-sm whitespace-pre-wrap")


def _entry_trace(entry: TraceEntry) -> None:
    match entry:
        case Applied(facts=facts):
            _section("ADVANCEMENT", _facts(facts))
        case Extended(facts=facts):
            _section("THE WORLD GREW", _facts(facts))
        case Turn():
            _turn_trace(entry)


def _turn_trace(turn: Turn) -> None:
    for step in turn.steps:
        _section(step.name.upper(), _output(step))
    _section("FACTS (private)", _facts(turn.facts))
    with ui.expansion("what each role was shown").classes("w-full mt-3"):
        for step in turn.steps:
            _section(step.name.upper(), step.prompt)


def _output(step: StepTrace) -> str:
    match step.output:
        case str() as text:
            return text
        case body:
            return json.dumps(body, indent=2)


def _facts(facts: Sequence[Fact]) -> str:
    lines = [f"- {fact.trace}" for fact in facts]
    return "\n".join(lines) or "- (none)"


def advancement_panel(session: GameSession, refresh: Callable[[], None]) -> None:
    """The one advancement panel; shown only when the engine plugs in a growth mechanic."""
    if session.drafted is not None:
        _review(session, session.drafted, refresh)
        return
    offers = session.offers()
    if not offers:
        ui.label("Nothing is on offer.").classes("opacity-70")
        return
    for offer in offers:
        _summary(offer)
        _intent_form(session, offer, refresh)


def _summary(offer: Offer) -> None:
    ui.label(offer.prompt).classes("text-sm font-bold")
    if offer.text:
        ui.label(offer.text).classes("text-sm opacity-70 whitespace-pre-wrap")


def _intent_form(session: GameSession, offer: Offer, refresh: Callable[[], None]) -> None:
    box = ui.textarea("How do you want to grow?").classes("w-full mt-3").props("outlined")

    async def propose() -> None:
        intent = (box.value or "").strip()
        if not intent:
            ui.notify("Say how you want to grow first.", type="warning")
            return
        # Checked at click time: a turn may have started after the panel rendered.
        if refuse_if_busy(session):
            return
        async with working(session):
            session.drafted = Drafted(offer=offer, proposal=await session.propose(offer, intent))
        refresh()

    ui.button("Propose", on_click=propose).props("color=primary")


def _review(session: GameSession, drafted: Drafted, refresh: Callable[[], None]) -> None:
    ui.label("Proposed changes").classes("text-sm font-bold mt-3")
    try:
        lines = [f"- {fact.trace}" for fact in session.preview(drafted)]
    except ValueError as stale:
        # A turn since the proposal may have changed the character from under the draft.
        lines = [f"This proposal no longer applies: {stale}. Discard it and propose again."]
    for line in lines:
        ui.label(line).classes("text-sm whitespace-pre-wrap")

    def discard() -> None:
        session.drafted = None
        refresh()

    def confirm() -> None:
        if refuse_if_busy(session):
            return
        try:
            _ = session.apply_proposal(drafted)
        except ValueError as error:
            ui.notify(str(error), type="negative", multi_line=True)
            return
        session.drafted = None
        refresh()

    with ui.row().classes("w-full mt-3").style("gap: 0.75rem"):
        ui.button("Discard", on_click=discard).props("flat")
        ui.button("Confirm", on_click=confirm).props("color=primary")


def state_panel(session: GameSession) -> None:
    ui.code(
        SavedGame.of(session.state).model_dump_json(indent=2),
        language="json",
    ).classes("w-full text-xs")


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
        live_turn(self.session, self.live_prompt, self.live_events)

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
            self.sheet,
            self.journal,
            self.trace,
            self.advancement,
            self.state,
        ):
            panel.refresh()


def _idle(busy: bool) -> bool:
    """Bound to `session.busy`, so the composer follows the turn through every exit `working`
    takes, including the failure it swallows."""
    return not busy


def on_step(view: GameView, step: str) -> None:
    view.session.step = step
    view.live_turn.refresh()
    if view.composer is not None:
        view.composer.props(f'placeholder="{_composer_placeholder(step)}"')


def on_event(view: GameView, event: MechanicEvent, loop: AbstractEventLoop) -> None:
    """Pydantic AI runs sync director tools off-loop, in an anyio worker thread: this callback
    fires there too, so the UI update it triggers must be scheduled back onto the event loop."""
    loop.call_soon_threadsafe(_apply_event, view, event)


def _apply_event(view: GameView, event: MechanicEvent) -> None:
    view.live_events.append(event)
    view.live_turn.refresh()
    _scroll(view)


def _scroll(view: GameView) -> None:
    if (transcript := view.transcript) is not None:
        # A method call on an existing element needs no NiceGUI slot; `ui.timer` here would.
        get_running_loop().call_later(0.1, lambda: transcript.scroll_to(percent=1.0))


def poll_art(view: GameView) -> None:
    """The illustration is generated after the turn commits, so the page watches for it to land."""
    shown = (view.session.scene_art(), view.session.scene_pending())
    if shown != view.shown_art:
        view.shown_art = shown
        view.scene.refresh()


async def submit(view: GameView, box: ui.input) -> None:
    session = view.session
    prompt = (box.value or "").strip()
    LOGGER.info("player submitted prompt: non_empty=%s busy=%s", bool(prompt), session.busy)
    if not prompt or refuse_if_busy(session):
        return
    box.value = ""
    # Quasar never saw the typed value change, so only an explicit push empties the composer.
    _ = box.run_method("updateValue")
    view.live_prompt, view.live_events = prompt, []
    view.live_turn.refresh()
    _scroll(view)
    loop = get_running_loop()
    async with working(session):
        was_offered = session.pending()
        await session.submit(
            prompt,
            on_step=lambda step: on_step(view, step),
            on_event=lambda event: on_event(view, event, loop),
        )
        if not was_offered and session.pending():
            ui.notify("Something is on offer. Check the advancement tab.")
    session.step = None
    view.live_prompt, view.live_events = None, []
    if view.composer is not None:
        view.composer.props(f'placeholder="{_composer_placeholder(None)}"')
    view.refresh_all()
    _scroll(view)


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

    # The header eats 4rem and the page its own padding, so a bare `h-screen` puts the input
    # row below the fold.
    with ui.splitter(value=55).classes("w-full").style("height: calc(100vh - 6rem)") as splitter:
        with splitter.before, ui.column().classes("w-full h-full p-4").style("gap: 0.5rem"):
            view.scene()
            with ui.scroll_area().classes("w-full flex-grow game-transcript") as transcript:
                view.chat()
                view.live_turn()
            with (
                ui.row()
                .classes("w-full no-wrap items-end game-composer q-pa-sm")
                .style("gap: 0.5rem")
            ):
                box = (
                    ui.input(placeholder=_composer_placeholder(None))
                    .classes("flex-grow")
                    .props("outlined autogrow type=textarea borderless")
                    .bind_enabled_from(session, "busy", backward=_idle)
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
                    .bind_enabled_from(session, "busy", backward=_idle)
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

    if session.media is not None:
        ui.timer(3.0, lambda: poll_art(view))
