import logging
from functools import partial
from pathlib import Path
from tempfile import mkdtemp

from nicegui import ui
from nicegui.events import UploadEventArguments, ValueChangeEventArguments

from aidm.app.launch import launch_target, load_catalog
from aidm.app.runtime import Runtime
from aidm.content.io import SOURCE_SUFFIXES, write_character
from aidm.state.creation import CreationStep, picked
from aidm.state.entities import Slug

from .widgets import labeled_value, page_header

LOGGER = logging.getLogger(__name__)


def character_page(runtime: Runtime) -> None:
    engine = runtime.engine
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

            def write(step_id: Slug, event: ValueChangeEventArguments[str | None]) -> None:
                picks[step_id] = (event.value or "").strip()

            def choose(step_id: Slug, event: ValueChangeEventArguments[str]) -> None:
                picks[step_id] = event.value
                _drop_stale(creation.steps(picks), picks)
                form.refresh()

            def field(step: CreationStep) -> None:
                given = picked(picks, step.id)
                if not step.options:
                    written = ui.input(
                        label=step.prompt,
                        placeholder=step.hint or "In your own words",
                        value=given,
                        on_change=partial(write, step.id),
                    )
                    # Refreshing per keystroke would take the focus away mid-word.
                    written.classes("w-full").props("outlined").on("blur", lambda: form.refresh())
                    return
                ui.select(
                    options={
                        option.id: f"{option.label} — {option.detail}"
                        if option.detail
                        else option.label
                        for option in step.options
                    },
                    value=given or None,
                    label=step.prompt,
                    on_change=partial(choose, step.id),
                ).classes("w-full")

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
                for step in creation.steps(picks):
                    field(step)
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


def _drop_stale(steps: tuple[CreationStep, ...], picks: dict[Slug, str]) -> None:
    """A new pack, or a skill moved onto its twin, can leave an answer its step no longer offers."""
    for step in steps:
        if step.options and picked(picks, step.id) not in {one.id for one in step.options}:
            _ = picks.pop(step.id, None)


def scenario_page(runtime: Runtime) -> None:
    """A premise or a document, one worldsmith call, and the game opens on the scene it wrote."""
    engine = runtime.engine
    catalog = load_catalog(runtime.settings, runtime.engines)
    written = catalog.characters
    with page_header("New scenario", engine.title):
        pass
    document: Path | None = None

    async def took(event: UploadEventArguments) -> None:
        nonlocal document
        # Saved to disk: the source reader opens a path, and a PDF cannot be parsed from bytes.
        path = Path(mkdtemp()) / Path(event.file.name).name
        await event.file.save(path)
        document = path
        ui.notify(f"Read {event.file.name}.")

    with ui.column().classes("w-full q-pa-lg items-center"):
        with ui.card().classes("q-pa-lg").style("width: min(60rem, 100%)"):
            title = ui.input(label="Title").classes("w-full").props("outlined")
            packs = ui.select(
                options={one.id: one.label for one in engine.packs},
                value=[one.id for one in engine.packs],
                label="Table sets",
                multiple=True,
            ).classes("w-full")
            character = ui.select(
                options={one.id: f"{one.title} — {one.subtitle}" for one in written},
                value=written[0].id if written else None,
                label="Character",
            ).classes("w-full")
            premise = (
                ui.textarea(label="Premise", placeholder="What is this adventure about?")
                .classes("w-full")
                .props("outlined autogrow")
            )
            ui.label("Or upload the adventure itself.").classes("text-sm opacity-70 q-mt-md")
            _ = (
                ui.upload(on_upload=took, max_files=1, auto_upload=True)
                .props(f'accept="{",".join(SOURCE_SUFFIXES)}"')
                .classes("w-full")
            )

            async def write() -> None:
                chosen = (title.value or "").strip()
                told = (premise.value or "").strip()
                if not chosen or not (told or document) or character.value is None:
                    ui.notify("A title, a character, and a premise or a document.", type="warning")
                    return
                button.props("loading")
                try:
                    name = await runtime.new_scenario(
                        chosen, told, document, packs.value, character.value
                    )
                    opened = launch_target(
                        load_catalog(runtime.settings, runtime.engines), name, character.value
                    )
                except (OSError, ValueError) as refused:
                    ui.notify(str(refused), type="negative", multi_line=True)
                    return
                finally:
                    button.props(remove="loading")
                LOGGER.info("scenario created: slug=%s", name)
                ui.navigate.to(opened.path)

            button = ui.button("Write the opening", icon="auto_stories", on_click=write).props(
                "color=primary"
            )
            ui.label("Writing takes several minutes.").classes("text-xs opacity-60")
            if not written:
                button.disable()
                ui.label("Make a character first.").classes("text-sm text-negative")
