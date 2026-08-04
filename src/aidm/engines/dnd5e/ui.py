from collections.abc import Callable, Sequence

from nicegui import ui

from aidm.core.engine import AdvancementPanel, AdvancementSubmit, CurrentState, entered_text

from .advancement import (
    Dnd5eAdvancement,
    Dnd5eAdvancementDecisions,
    Section,
    benefit_sections,
    dump_decision,
    plan_sections,
)
from .content.records.character import ProgressionChoice
from .progression import AdvancementPlan, LevelUpPreview


def advancement_panel_for(advancement: Dnd5eAdvancement) -> AdvancementPanel:
    def render(state: CurrentState, submit: AdvancementSubmit, refresh: Callable[[], None]) -> None:
        current = state()
        status = advancement.status(current)
        ui.label(f"{current.player.name} — {status.headline}").classes("text-sm font-bold")
        ui.linear_progress(value=status.progress, show_value=False).classes("w-full")
        for line in status.detail:
            ui.label(line).classes("text-sm opacity-70 whitespace-pre-line")
        if not advancement.available(current):
            return
        try:
            preview = advancement.preview(current)
        except ValueError as error:
            ui.label(f"Cannot read the advancement: {error}").classes("text-negative text-sm")
            return
        ui.label(f"Level {preview.benefits.level} preview").classes("text-h6 q-mt-md")
        _sections(benefit_sections(preview.benefits))
        _choices_card(advancement, state, preview, submit, refresh)

    return render


def _sections(sections: Sequence[Section]) -> None:
    for section in sections:
        with ui.card().classes("w-full"):
            ui.label(section.heading).classes("font-bold")
            for line in section.lines:
                ui.label(line).classes("text-sm whitespace-pre-line")


def _choices_card(
    advancement: Dnd5eAdvancement,
    state: CurrentState,
    preview: LevelUpPreview,
    submit: AdvancementSubmit,
    refresh: Callable[[], None],
) -> None:
    with ui.card().classes("w-full"):
        ui.label(f"Level {preview.benefits.level}").classes("font-bold")
        if not preview.choices:
            ui.label("No decisions are required.").classes("text-xs opacity-60")
        inputs = {choice.id: _choice_fields(choice) for choice in preview.choices}
        ui.button(
            f"Review level {preview.benefits.level}",
            on_click=lambda: _on_review(advancement, state, inputs, submit, refresh),
        ).props("color=primary")


def _choice_fields(choice: ProgressionChoice) -> list[ui.select]:
    if choice.distinct and choice.choose > 1:
        ui.label(f"Choose {choice.choose} different options.").classes("text-xs opacity-60")
    options = {option.key: option.label for option in choice.options}
    return [
        ui.select(options=options, label=_numbered(choice, number)).classes("w-full")
        for number in range(choice.choose)
    ]


def _numbered(choice: ProgressionChoice, number: int) -> str:
    if choice.choose == 1:
        return choice.prompt
    return f"{choice.prompt} ({number + 1} of {choice.choose})"


def _on_review(
    advancement: Dnd5eAdvancement,
    state: CurrentState,
    inputs: dict[str, list[ui.select]],
    submit: AdvancementSubmit,
    refresh: Callable[[], None],
) -> None:
    values: dict[str, tuple[str, ...]] = {}
    for choice_id, elements in inputs.items():
        filled = tuple(
            text for element in elements if (text := entered_text(element.value)) is not None
        )
        if len(filled) != len(elements):
            ui.notify("Complete every field first.", type="warning")
            return
        values[choice_id] = filled
    try:
        decisions = Dnd5eAdvancementDecisions(decisions=values)
        plan = advancement.plan(state(), decisions.decisions)
    except ValueError as error:
        ui.notify(str(error), type="negative", multi_line=True)
        return
    _confirm(plan, decisions, submit, refresh)


def _confirm(
    plan: AdvancementPlan,
    decisions: Dnd5eAdvancementDecisions,
    submit: AdvancementSubmit,
    refresh: Callable[[], None],
) -> None:
    with (
        ui.dialog() as dialog,
        ui.card().style(
            "height: 80vh; width: min(48rem, 95vw); display: flex; flex-direction: column;"
        ),
    ):
        ui.label(f"Confirm level {plan.benefits.level}").classes("text-h6")
        with ui.scroll_area().style("flex: 1; min-height: 0;"):
            _sections(plan_sections(plan))
        with ui.element("div").style(
            "position: sticky; bottom: 0; padding-top: 1rem; "
            "border-top: 1px solid var(--q-dark-page);"
        ):
            with ui.row().classes("w-full justify-end").style("gap: 0.75rem"):
                ui.button("Back", on_click=dialog.close).props("flat")
                ui.button(
                    f"Confirm level {plan.benefits.level}",
                    on_click=lambda: _on_confirm(decisions, submit, dialog, refresh),
                ).props("color=primary")
    dialog.open()


def _on_confirm(
    decisions: Dnd5eAdvancementDecisions,
    submit: AdvancementSubmit,
    dialog: ui.dialog,
    refresh: Callable[[], None],
) -> None:
    if submit(dump_decision(decisions)):
        dialog.close()
        refresh()
