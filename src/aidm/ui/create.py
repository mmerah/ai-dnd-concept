import logging
from collections.abc import Callable
from pathlib import Path

from nicegui import ui
from nicegui.events import ValueChangeEventArguments
from pydantic import JsonValue

from aidm.app.session import Runtime
from aidm.content.authored import CreatedCharacter
from aidm.content.store import write_character
from aidm.state.base import EngineId, Slug, text_slug
from aidm.state.creation import CreationStep

from .panels import show_engine_badge

LOGGER = logging.getLogger(__name__)


def creation_page(runtime: Runtime, engine_id: EngineId) -> None:
    engine = runtime.engine(engine_id)
    with ui.header().classes("items-center").style("gap: 1rem"):
        ui.button(icon="home", on_click=lambda: ui.navigate.to("/")).props("flat color=white round")
        ui.label("New character").classes("text-lg font-bold")
        show_engine_badge(engine.badge)
    creation = engine.creation
    with ui.column().classes("w-full q-pa-lg items-center"):
        if creation is None:
            with ui.card().style("width: min(48rem, 100%)").classes("q-pa-lg"):
                ui.label("These rules offer no character creation.").classes("text-negative")
            return
        picks: dict[Slug, tuple[Slug, ...]] = {}
        with ui.row().classes("no-wrap items-start").style("width: min(80rem, 100%); gap: 1rem"):
            with ui.card().classes("q-pa-lg").style("flex: 1; min-width: 0"):
                name = (
                    ui.input(label="Name", on_change=lambda _: preview.refresh())
                    .classes("w-full")
                    .props("outlined")
                )
                brief = (
                    ui.input(
                        label="Brief",
                        placeholder="Who are they, in one sentence?",
                        on_change=lambda _: preview.refresh(),
                    )
                    .classes("w-full")
                    .props("outlined")
                )

                @ui.refreshable
                def form() -> None:
                    steps = creation.steps(picks)
                    offered = {step.id for step in steps}
                    for stale in [step_id for step_id in picks if step_id not in offered]:
                        del picks[stale]
                    for step in steps:
                        _step_select(step, picks, refresh_form_and_preview)
                    ui.button("Create", icon="person_add", on_click=create).props(
                        "color=primary"
                    ).classes("q-mt-md")

                def create() -> None:
                    title = (name.value or "").strip()
                    if not title:
                        ui.notify("Name the character.", type="warning")
                        return
                    try:
                        created = creation.create(title, (brief.value or "").strip(), picks)
                        slug = text_slug(title, _taken(runtime.config.characters_dir))
                        write_character(runtime.config.characters_dir, slug, engine_id, created)
                    except ValueError as refused:
                        ui.notify(str(refused), type="negative")
                        return
                    LOGGER.info("character created: slug=%s engine=%s", slug, engine_id)
                    ui.navigate.to("/")

                @ui.refreshable
                def preview() -> None:
                    ui.label((name.value or "").strip() or "Unnamed").classes("text-lg font-bold")
                    if brief_text := (brief.value or "").strip():
                        ui.label(brief_text).classes("text-sm opacity-70")
                    for step in creation.steps(picks):
                        labels = {option.id: option.label for option in step.options}
                        chosen = ", ".join(
                            labels.get(pick, pick) for pick in picks.get(step.id, ())
                        )
                        dim = "" if chosen else " opacity-50"
                        with ui.row().classes(f"items-baseline{dim}").style("gap: 0.5rem"):
                            ui.label(step.prompt).classes("text-sm font-bold")
                            ui.label(chosen or "—").classes("text-sm")
                    try:
                        created = creation.create(
                            (name.value or "").strip() or "Unnamed", brief_text, picks
                        )
                    except ValueError as refused:
                        ui.label(f"Not ready yet: {refused}").classes("text-sm opacity-50")
                        return
                    ui.separator().classes("q-my-sm")
                    for label, text in _preview_lines(created):
                        with ui.row().classes("items-baseline").style("gap: 0.5rem"):
                            ui.label(label).classes("text-sm font-bold")
                            if text:
                                ui.label(text).classes("text-sm")

                def refresh_form_and_preview() -> None:
                    form.refresh()
                    preview.refresh()

                form()
            with ui.card().classes("q-pa-lg").style("flex: 1; min-width: 0"):
                preview()


def _preview_lines(created: CreatedCharacter) -> list[tuple[str, str]]:
    """One (label, text) row per fact, engine-agnostic: the overlay is an opaque dict here."""
    lines = [(trait.name, trait.text) for trait in created.profile.traits]
    for key, value in created.overlay.character.items():
        if isinstance(value, dict):
            if "current" in value and "maximum" in value:
                lines.append((key, f"{value['current']}/{value['maximum']}"))
            else:
                lines.extend((key, f"{inner}: {value[inner]}") for inner in value)
        elif isinstance(value, list):
            lines.extend((key, _element(element)) for element in value)
        else:
            lines.append((key, str(value)))
    return lines


def _element(element: JsonValue) -> str:
    if isinstance(element, dict) and {"pack", "collection", "index"} <= element.keys():
        return f"{element['pack']}/{element['collection']}/{element['index']}"
    return str(element)


def _step_select(
    step: CreationStep,
    picks: dict[Slug, tuple[Slug, ...]],
    refresh: Callable[[], object],
) -> None:
    options = {
        option.id: f"{option.label} — {option.detail}" if option.detail else option.label
        for option in step.options
    }
    held = picks.get(step.id, ())
    value = list(held) if step.choose > 1 else (held[0] if held else None)

    def changed(event: ValueChangeEventArguments[object]) -> None:
        chosen = event.value
        if isinstance(chosen, list):
            picks[step.id] = tuple(item for item in chosen if isinstance(item, str))  # pyright: ignore[reportUnknownVariableType]
        elif isinstance(chosen, str):
            picks[step.id] = (chosen,)
        else:
            picks.pop(step.id, None)
        refresh()

    ui.select(
        options=options,
        value=value,
        label=step.prompt,
        multiple=step.choose > 1,
        on_change=changed,  # pyright: ignore[reportUnknownArgumentType]
    ).classes("w-full")


def _taken(directory: Path) -> tuple[str, ...]:
    if not directory.is_dir():
        return ()
    return tuple(path.name for path in directory.iterdir() if path.is_dir())
