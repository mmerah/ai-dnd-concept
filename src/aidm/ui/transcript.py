from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, replace
from functools import partial
from typing import Self

from nicegui import ui

from aidm.app.runtime import GameService
from aidm.config import Role
from aidm.core.entities import Slug
from aidm.core.facts import DiceEvent, Fact, cards
from aidm.core.play import DecisionOption, Exchange, Marked
from aidm.core.views import PlayerView
from aidm.ui.widgets import avatar, heading, media_url

STEP_COPY: dict[Role, tuple[str, str]] = {
    "master": (
        "Game Master",
        "Decides what your action does: who reacts, what changes, "
        "and if the dice decide the result.",
    ),
    "narrator": ("Narrator", "Writes what you see and hear this turn."),
    "worldsmith": (
        "Worldsmith",
        "Writes the next scene or region, or what the game master asks for. The text shows "
        "where the story goes and who waits there. This step is slow. A few minutes is usual.",
    ),
}
MARK_LABELS: dict[Marked, str] = {
    "opening": "(the story begins)",
    "story": "(the story goes on)",
    "interjection": "(the party speaks)",
}
DECISION_ROW = "game-card game-decision w-full items-center no-wrap game-gap-md"
READ_ICONS = {False: "play_arrow", True: "stop"}


@dataclass(frozen=True, slots=True, kw_only=True)
class Observed:
    working_role: Role | None
    facts: int
    exchanges: int
    action: DecisionOption | None
    ending: str | None

    @classmethod
    def of(cls, session: GameService, view: PlayerView, history: Sequence[Exchange]) -> Self:
        return cls(
            working_role=session.working_role,
            facts=0 if session.turn is None else len(session.turn.facts),
            exchanges=len(history),
            action=view.action,
            ending=view.ending,
        )


def can_type(player: PlayerView, working_role: Role | None) -> bool:
    decision = player.decision
    return (
        working_role is None
        and (decision is None or decision.allows_text)
        and player.ending is None
    )


def standing_proposal(
    history: Sequence[Exchange], player: PlayerView, working_role: Role | None
) -> Exchange | None:
    newest = history[-1] if history else None
    if newest is None or not newest.proposal:
        return None
    return newest if can_type(player, working_role) and player.decision is None else None


def placeholder(player: PlayerView, working_role: Role | None) -> str:
    if player.ending is not None:
        return "The game is over. Restart it from the menu."
    if working_role is not None:
        return f"{STEP_COPY[working_role][0]} is working..."
    if player.decision is None:
        return "What do you do?"
    if player.decision.allows_text:
        return "The game is waiting on your answer."
    return "Choose an option above."


def chat(
    session: GameService,
    view: PlayerView,
    history: Sequence[Exchange],
    *,
    reading: str,
    accept: Callable[[str], Awaitable[None]],
    read: Callable[[Exchange, int], None],
) -> dict[str, ui.button]:
    """Returns each line's read button by its clip url, so a reading change flips the icon."""
    buttons: dict[str, ui.button] = {}
    if not history:
        ui.label(view.premise).classes("text-sm italic opacity-70")
    # The live decision widget sits directly below the last exchange, so it needs no pause line.
    last = history[-1] if history and view.decision is not None else None
    player = view.player
    for exchange in history:
        if exchange.mark:
            ui.label(MARK_LABELS[exchange.mark]).classes(
                "w-full text-center text-xs italic opacity-60"
            )
        else:
            bubble(session, player.id, player.name, exchange.words, sent=True)
        for fact in cards(exchange.facts):
            card(fact)
        clips = session.clips(exchange)
        for index, line in enumerate(exchange.lines):
            message = bubble(session, line.speaker_id, line.speaker, line.text, sent=False)
            if (clip := clips[index]) is None:
                continue
            url = media_url(clip)
            with message.add_slot("stamp"):
                buttons[url] = read_button(
                    reading=url == reading, on_click=partial(read, exchange, index)
                )
        if exchange.decision and exchange is not last:
            ui.label(f"Paused: {exchange.decision}").classes("text-xs italic opacity-60")
    if (proposed := standing_proposal(history, view, session.working_role)) is not None:
        with ui.row().classes(DECISION_ROW):
            ui.icon("record_voice_over").classes("game-card-icon")
            ui.label(f"{proposed.lines[0].speaker} proposes: {proposed.proposal}").classes(
                "text-sm"
            )
            ui.button("Accept", on_click=partial(accept, proposed.proposal)).props("outline dense")
    return buttons


def read_button(*, reading: bool, on_click: Callable[[], None]) -> ui.button:
    """The icon alone follows the reading: a stop square while its line is read."""
    return (
        ui.button(icon=READ_ICONS[reading], on_click=on_click, color=None)
        .props('flat round dense size=sm aria-label="Read from here"')
        .classes("game-read")
        .tooltip("Read from here")
    )


def live_turn(session: GameService, view: PlayerView, elapsed: float) -> ui.label | None:
    turn = session.turn
    player = view.player
    if turn is not None:
        bubble(session, player.id, player.name, turn.words, sent=True)
        shown = cards(turn.facts)
        for fact in shown:
            card(fact, live=fact is shown[-1])
    elif session.intent:
        bubble(session, player.id, player.name, session.intent, sent=True)
    if session.working_role is None:
        return None
    return inline_status(session.working_role, elapsed)


def journal(history: Sequence[Exchange]) -> None:
    heading("Chronicle")
    for number, exchange in reversed(list(enumerate(history, start=1))):
        title = MARK_LABELS[exchange.mark] if exchange.mark else exchange.words
        with ui.expansion(f"turn {number}: {title}").classes("w-full game-card"):
            for line in exchange.lines:
                if line.speaker_id is None:
                    ui.label(line.text).classes("whitespace-pre-wrap text-sm")
                else:
                    with ui.row().classes("items-start no-wrap game-gap-sm"):
                        ui.label(f"{line.speaker}:").classes("font-bold whitespace-nowrap text-sm")
                        ui.label(line.text).classes("whitespace-pre-wrap text-sm")


def card(fact: Fact, *, live: bool = False) -> None:
    headline, *detail = fact.card.split("\n")
    with ui.column().classes("game-card w-full game-gap-sm"):
        ui.label(headline).classes("text-sm font-bold")
        for line in detail:
            ui.label(line).classes("text-xs opacity-80")
        if fact.dice:
            with ui.row().classes("items-start game-gap-2xl"):
                for group in fact.dice:
                    dice_group(group, live=live)


def dice_group(die: DiceEvent, *, live: bool) -> None:
    with ui.column().classes("game-gap-2xs"):
        ui.label(die.label).classes("text-xs opacity-60")
        with ui.row().classes("no-wrap game-gap-sm"):
            for index, (face, value) in enumerate(zip(die.faces, die.rolled, strict=True)):
                with ui.column().classes(
                    "game-die game-gap-0"
                    + (" game-die-kept" if index in die.highlight else "")
                    + (" game-die-live" if live else "")
                ):
                    ui.label(f"d{face}").classes("game-die-face")
                    ui.label(str(value)).classes("game-die-value")


def bubble(
    session: GameService, speaker_id: Slug | None, name: str, text: str, *, sent: bool
) -> ui.chat_message:
    narration = speaker_id is None
    icon = None if narration else session.icon(speaker_id)
    chat_name = "DM" if narration else name
    message = ui.chat_message(text, name=chat_name, sent=sent).classes(
        "w-full game-message" + (" game-narration" if narration else "")
    )
    with message.add_slot("avatar"):
        avatar(icon, None if narration else chat_name)
    return message


def inline_status(step: Role, elapsed: float) -> ui.label:
    label, description = STEP_COPY[step]
    with ui.row().classes("items-center no-wrap q-py-xs game-gap-md"):
        ui.spinner(size="1.1rem")
        ui.label(label).classes("text-sm font-bold")
        ticker = ui.label(clock(elapsed)).classes("text-xs font-mono")
    ui.label(description).classes("text-xs opacity-70")
    return ticker


def clock(seconds: float) -> str:
    minutes, rest = divmod(int(seconds), 60)
    return f"{minutes}:{rest:02d}"


def near_end(position: float, size: float, container: float, slack: float = 48) -> bool:
    return size - position - container <= slack


def draft_spent(draft: str, newest_prompt: str) -> bool:
    return bool(draft) and draft == newest_prompt


def whole_page(now: Observed, seen: Observed) -> bool:
    """False when only the fact count moved: the live turn is then the one part that can differ."""
    return replace(now, facts=0) != replace(seen, facts=0)


def rolled_since(facts: Sequence[Fact], seen: int) -> bool:
    return any(fact.dice for fact in cards(facts[seen:]))
