import logging
from functools import partial

from nicegui import ui

from aidm.app.runtime import Runtime
from aidm.content.io import write_character
from aidm.state.creation import picked
from aidm.state.entities import EngineId, Slug

from .widgets import decision_widget, labeled_value, page_header

LOGGER = logging.getLogger(__name__)


def character_page(runtime: Runtime, engine_id: str) -> None:
    engine = runtime.engines.get(EngineId(engine_id))
    if engine is None:
        raise ValueError(f"unknown engine {engine_id!r}")
    with page_header("New character", engine.title):
        pass
    creation = engine.creation
    picks: dict[Slug, str] = {}
    with ui.column().classes("w-full q-pa-lg items-center"):
        with ui.card().classes("q-pa-lg").style("width: min(60rem, 100%)"):
            name = ui.input(label="Name").classes("w-full").props("outlined")
            brief = (
                ui.input(label="Brief", placeholder="Who are they, in one sentence?")
                .classes("w-full")
                .props("outlined")
            )

            def answer(step_id: Slug, given: str) -> None:
                picks[step_id] = given
                form.refresh()

            def rewind(step_id: Slug) -> None:
                for key in list(picks)[list(picks).index(step_id) :]:
                    del picks[key]
                form.refresh()

            def create() -> None:
                title = (name.value or "").strip()
                if not title:
                    ui.notify("Name the character.", type="warning")
                    return
                try:
                    envelope, _ = creation.created(title, (brief.value or "").strip(), picks)
                    write_character(runtime.settings.characters_dir, envelope)
                except ValueError as refused:
                    ui.notify(str(refused), type="negative")
                    return
                LOGGER.info("character created: slug=%s engine=%s", envelope.id, engine.id)
                ui.navigate.to("/")

            @ui.refreshable
            def form() -> None:
                steps = creation.steps(picks)
                for step in steps:
                    if given := picked(picks, step.id):
                        shown = next((o.label for o in step.options if o.id == given), given)
                        with (
                            ui.row().classes("cursor-pointer").on("click", partial(rewind, step.id))
                        ):
                            labeled_value(step.prompt, shown)
                asking = next((step for step in steps if not picked(picks, step.id)), None)
                if asking is not None:
                    decision_widget(
                        asking.prompt,
                        asking.options,
                        partial(answer, asking.id),
                        text_hint=None if asking.options else asking.hint or "In your own words",
                        detail_shown=True,
                    )
                    return
                try:
                    _, preview = creation.created(
                        (name.value or "").strip() or "Unnamed",
                        (brief.value or "").strip(),
                        picks,
                    )
                except ValueError as refused:
                    ui.label(f"Not ready yet: {refused}").classes("text-sm opacity-50")
                    return
                ui.separator().classes("q-my-sm")
                for label, text in preview.rows:
                    labeled_value(label, text)
                ui.button("Create", icon="person_add", on_click=create).props("color=primary")

            form()
