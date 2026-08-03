from collections.abc import Callable, Sequence

from nicegui import ui

from aidm.advancement import (
    AdvancementChoice,
    AdvancementOption,
    AdvancementReview,
    Block,
    FormField,
    SelectField,
    TextField,
)
from aidm.application import GameSession

# Both carry a `value`; the renderer narrows it to text at the one place it is read.
type Field = ui.select | ui.input
type Inputs = dict[str, list[Field]]


def advancement_panel(session: GameSession, refresh: Callable[[], None]) -> None:
    """One renderer for every engine: status, the offered options, then the confirm dialog."""
    engine = session.engine
    status = engine.advancement_status(session.state)
    ui.label(f"{session.state.player.name} — {status.headline}").classes("text-sm font-bold")
    ui.linear_progress(value=status.progress, show_value=False).classes("w-full")
    for line in status.detail:
        ui.label(line).classes("text-sm opacity-70 whitespace-pre-line")
    if not engine.advancement_available(session.state):
        return
    try:
        form = engine.advancement_form(session.state)
    except ValueError as error:
        ui.label(f"Cannot read the advancement: {error}").classes("text-negative text-sm")
        return
    ui.label(form.title).classes("text-h6 q-mt-md")
    _blocks(form.blocks)
    with ui.column().classes("w-full").style("gap: 0.75rem"):
        for option in form.options:
            _option(session, refresh, option)


def _blocks(blocks: Sequence[Block]) -> None:
    for block in blocks:
        with ui.card().classes("w-full"):
            ui.label(block.heading).classes("font-bold")
            for line in block.lines:
                ui.label(line).classes("text-sm whitespace-pre-line")


def _option(session: GameSession, refresh: Callable[[], None], option: AdvancementOption) -> None:
    with ui.card().classes("w-full"):
        ui.label(option.heading).classes("font-bold")
        if option.note:
            ui.label(option.note).classes("text-xs opacity-60")
        inputs: Inputs = {field.id: _field(field) for field in option.fields}
        ui.button(
            option.action,
            on_click=lambda: _review(session, refresh, option, inputs),
        ).props("color=primary")


def _field(field: FormField) -> list[Field]:
    match field:
        case SelectField():
            if field.note:
                ui.label(field.note).classes("text-xs opacity-60")
            return [
                ui.select(
                    options={option.key: option.label for option in field.options},
                    label=_numbered(field, number),
                ).classes("w-full")
                for number in range(field.choose)
            ]
        case TextField():
            return [ui.input(label=field.label).classes("w-full")]


def _numbered(field: SelectField, number: int) -> str:
    if field.choose == 1:
        return field.label
    return f"{field.label} ({number + 1} of {field.choose})"


def _review(
    session: GameSession,
    refresh: Callable[[], None],
    option: AdvancementOption,
    inputs: Inputs,
) -> None:
    values: dict[str, tuple[str, ...]] = {}
    for field_id, elements in inputs.items():
        filled = tuple(text for element in elements if (text := _text(element.value)) is not None)
        if len(filled) != len(elements):
            ui.notify("Complete every field first.", type="warning")
            return
        values[field_id] = filled
    choice = AdvancementChoice(option_id=option.id, values=values)
    try:
        review = session.engine.advancement_review(session.state, choice)
    except ValueError as error:
        ui.notify(str(error), type="negative", multi_line=True)
        return
    _confirm(session, refresh, review)


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _confirm(session: GameSession, refresh: Callable[[], None], review: AdvancementReview) -> None:
    with (
        ui.dialog() as dialog,
        ui.card().style(
            "height: 80vh; width: min(48rem, 95vw); display: flex; flex-direction: column;"
        ),
    ):
        ui.label(review.title).classes("text-h6")
        with ui.scroll_area().style("flex: 1; min-height: 0;"):
            _blocks(review.blocks)
        with ui.element("div").style(
            "position: sticky; bottom: 0; padding-top: 1rem; "
            "border-top: 1px solid var(--q-dark-page);"
        ):
            with ui.row().classes("w-full justify-end").style("gap: 0.75rem"):
                ui.button("Back", on_click=dialog.close).props("flat")
                ui.button(
                    review.confirm_label,
                    on_click=lambda: _commit(session, review, dialog, refresh),
                ).props("color=primary")
    dialog.open()


def _commit(
    session: GameSession,
    review: AdvancementReview,
    dialog: ui.dialog,
    refresh: Callable[[], None],
) -> None:
    if session.busy:
        ui.notify("Finish the current turn first.", type="warning")
        return
    try:
        _ = session.advance(review.decision)
    except (TypeError, ValueError) as error:
        ui.notify(str(error), type="negative", multi_line=True)
        return
    dialog.close()
    refresh()
