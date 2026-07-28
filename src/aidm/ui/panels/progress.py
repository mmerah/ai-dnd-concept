from nicegui import ui

from ...content.records import ProgressionChoice
from ...domain.models import MAX_LEVEL
from ..session import Session
from .state import state_panel


@ui.refreshable
def progress_panel(session: Session) -> None:
    player = session.app.state.player
    current = player.progression
    if current is None:
        ui.label("This character has no class, so there is nothing to advance.")
        return
    ui.label(f"{player.name} — level {current.level}").classes("text-sm font-bold")
    if current.level >= MAX_LEVEL:
        ui.label(f"Level {MAX_LEVEL} is the last.").classes("opacity-60")
        return

    level = current.level + 1
    try:
        choices = session.app.pending_choices()
    except ValueError as exc:
        ui.label(f"Cannot read level {level}: {exc}").classes("text-negative")
        return
    picks = {choice.id: _selects(choice) for choice in choices}
    ui.button(f"advance to level {level}", on_click=lambda: _advance(session, picks))


def _selects(choice: ProgressionChoice) -> list[ui.select]:
    """Use separate selects because a choice may repeat an option."""
    return [
        ui.select(
            options={option.key: option.label for option in choice.options},
            label=f"{choice.prompt} ({n + 1} of {choice.choose})",
        ).classes("w-full")
        for n in range(choice.choose)
    ]


def _advance(session: Session, picks: dict[str, list[ui.select]]) -> None:
    decisions = {id: tuple(str(s.value) for s in selects) for id, selects in picks.items()}
    try:
        session.app.advance(decisions)
    except ValueError as exc:
        ui.notify(str(exc), type="negative", multi_line=True)
        return
    progress_panel.refresh()
    state_panel.refresh()
