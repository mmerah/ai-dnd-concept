from collections.abc import Callable

from nicegui import ui
from pydantic import BaseModel

from ..session_model import Session


def confirm_advancement(
    session: Session,
    decisions: BaseModel,
    refresh: Callable[[], None],
    title: str,
    confirm_label: str,
    body: Callable[[], None],
) -> None:
    """Review and commit an advancement; shared by every engine's renderer."""
    with (
        ui.dialog() as dialog,
        ui.card().style(
            "height: 80vh; width: min(48rem, 95vw); display: flex; flex-direction: column;"
        ),
    ):
        ui.label(title).classes("text-h6")
        with ui.scroll_area().style("flex: 1; min-height: 0;"):
            body()
        with ui.element("div").style(
            "position: sticky; bottom: 0; padding-top: 1rem; "
            "border-top: 1px solid var(--q-dark-page);"
        ):
            with ui.row().classes("w-full justify-end").style("gap: 0.75rem"):
                ui.button("Back", on_click=dialog.close).props("flat")
                ui.button(
                    confirm_label,
                    on_click=lambda: _commit(session, decisions, dialog, refresh),
                ).props("color=primary")
    dialog.open()


def _commit(
    session: Session,
    decisions: BaseModel,
    dialog: ui.dialog,
    refresh: Callable[[], None],
) -> None:
    if session.busy:
        ui.notify("Finish the current turn first.", type="warning")
        return
    try:
        _ = session.app.advance(decisions)
    except (TypeError, ValueError) as error:
        ui.notify(str(error), type="negative", multi_line=True)
        return
    dialog.close()
    refresh()
