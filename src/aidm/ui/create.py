import logging
import shutil
from collections.abc import Callable
from functools import partial
from pathlib import Path
from tempfile import mkdtemp

from nicegui import ui
from nicegui.events import UploadEventArguments, ValueChangeEventArguments

from aidm.app.launch import LauncherCatalog, LaunchTarget
from aidm.app.runtime import Runtime
from aidm.core.creation import CreationStep, picked
from aidm.core.entities import EngineId, Refusal, Slug, content_id, parse
from aidm.core.io import SOURCE_SUFFIXES
from aidm.core.model import PackSelection, ScenarioMeta
from aidm.ui import theme
from aidm.ui.widgets import game_path, heading, labeled_value, page_body, page_header, page_intro

LOGGER = logging.getLogger(__name__)


class CharacterForm:
    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime
        self.engine_id = runtime.default_engine()
        self.picks: dict[Slug, str] = {}
        self.name: ui.input
        self.brief: ui.input
        self.ready: bool = False
        self.create_button: ui.button | None = None

    def build(self) -> None:
        with page_header("New character", look=self.runtime.engines[self.engine_id].look):
            pass
        with page_body():
            page_intro(
                "Character",
                "New character",
                "Name them, pick their rules, and answer what the rules ask.",
            )
            with ui.card().classes("w-full"):
                _engine_select(self.runtime, self.engine_id, self.choose_engine)
                self.name = ui.input(label="Name").classes("w-full")
                self.brief = ui.input(
                    label="Brief", placeholder="Who are they, in one sentence?"
                ).classes("w-full")
                self.steps()
                heading("Preview")
                self.preview()
                # Outside the preview refreshable: a rebuild on blur must not destroy button focus.
                self.create_button = (
                    ui.button("Create", icon="person_add", on_click=self.create)
                    .props("color=primary")
                    .classes("self-end")
                )
                self.create_button.set_visibility(self.ready)

    def choose_engine(self, event: ValueChangeEventArguments[str]) -> None:
        self.engine_id = EngineId(event.value)
        theme.set_look(self.runtime.engines[self.engine_id].look)
        # The steps come from the engine, so an answer to the old ones means nothing.
        self.picks.clear()
        self.steps.refresh()
        self.preview.refresh()

    def write(self, step_id: Slug, event: ValueChangeEventArguments[str | None]) -> None:
        self.picks[step_id] = (event.value or "").strip()

    def choose(self, step_id: Slug, event: ValueChangeEventArguments[str]) -> None:
        self.picks[step_id] = event.value
        _drop_stale(self.runtime.engines[self.engine_id].creation_steps(self.picks), self.picks)
        self.steps.refresh()
        self.preview.refresh()

    def field(self, step: CreationStep) -> None:
        given = picked(self.picks, step.id)
        if not step.options:
            typed = ui.input(
                label=step.label,
                placeholder=step.hint or "In your own words",
                value=given,
                on_change=partial(self.write, step.id),
            )
            # Rebuilding the whole form on blur would destroy the field Tab just moved to.
            typed.classes("w-full").on("blur", self.preview.refresh)
            return
        chosen = ui.select(
            options={
                option.id: f"{option.label} — {option.detail}" if option.detail else option.label
                for option in step.options
            },
            value=given or None,
            label=step.label,
            on_change=partial(self.choose, step.id),
        ).classes("w-full")
        if step.hint:
            chosen.props(f'hint="{step.hint}"')

    def create(self) -> None:
        title = (self.name.value or "").strip()
        if not title:
            ui.notify("Name the character.", type="warning")
            return
        try:
            made = self.runtime.engines[self.engine_id].create_character(
                title, (self.brief.value or "").strip(), self.picks
            )
            self.runtime.library.write_character(made)
        except Refusal as refused:
            ui.notify(str(refused), type="negative")
            return
        LOGGER.info("character created: slug=%s engine=%s", made.id, made.engine)
        ui.navigate.to("/")

    @ui.refreshable_method
    def steps(self) -> None:
        engine = self.runtime.engines[self.engine_id]
        for step in engine.creation_steps(self.picks):
            self.field(step)

    @ui.refreshable_method
    def preview(self) -> None:
        engine = self.runtime.engines[self.engine_id]
        try:
            preview = engine.preview_character(
                engine.create_character(
                    (self.name.value or "").strip() or "Unnamed",
                    (self.brief.value or "").strip(),
                    self.picks,
                )
            )
        except Refusal as refused:
            ui.label(f"Not ready yet: {refused}").classes("text-sm opacity-50")
            self.ready = False
        else:
            for label, text in preview:
                labeled_value(label, text)
            self.ready = True
        if self.create_button is not None:
            self.create_button.set_visibility(self.ready)


class ScenarioForm:
    def __init__(self, runtime: Runtime, catalog: LauncherCatalog) -> None:
        self.runtime = runtime
        self.catalog = catalog
        self.engine_id = runtime.default_engine()
        self.document: Path | None = None
        self.uploads: Path | None = None
        self.title: ui.input
        self.primary: ui.select | None = None
        self.supplements: ui.select | None = None
        self.pack_labels: dict[str, str] = {}
        self.character: ui.select
        self.premise: ui.textarea
        self.scope: ui.textarea
        self.style: ui.input
        self.voice: ui.input
        self.button: ui.button

    def build(self) -> None:
        with page_header("New scenario", look=self.runtime.engines[self.engine_id].look):
            pass
        with page_body():
            page_intro(
                "Scenario",
                "New scenario",
                "Describe the adventure, or upload one, and the worldsmith writes its opening.",
            )
            with ui.card().classes("w-full"):
                _engine_select(self.runtime, self.engine_id, self.choose_engine)
                self.form()

    async def uploaded(self, event: UploadEventArguments) -> None:
        # The source reader opens a path, and a PDF cannot be parsed from bytes.
        if self.uploads is None:
            self.uploads = Path(mkdtemp())
        if self.document is not None:
            self.document.unlink(missing_ok=True)
        path = self.uploads / Path(event.file.name).name
        await event.file.save(path)
        self.document = path
        ui.notify(f"Read {event.file.name}.")

    def choose_engine(self, event: ValueChangeEventArguments[str]) -> None:
        self.engine_id = EngineId(event.value)
        theme.set_look(self.runtime.engines[self.engine_id].look)
        self.form.refresh()

    def choose_primary(self, event: ValueChangeEventArguments[str]) -> None:
        if self.supplements is None:
            return
        current: list[str] = self.supplements.value or []
        options = self._supplement_options(event.value)
        self.supplements.set_options(  # pyright: ignore[reportUnknownMemberType]
            options, value=[pick for pick in current if pick != event.value]
        )

    def _supplement_options(self, primary: str) -> dict[str, str]:
        return {pick: label for pick, label in self.pack_labels.items() if pick != primary}

    @ui.refreshable_method
    def form(self) -> None:
        engine = self.runtime.engines[self.engine_id]
        characters = self.catalog.characters_for(self.engine_id)
        self.title = ui.input(label="Title").classes("w-full")
        self.pack_labels = {pack.id: pack.label for pack in engine.pack_options()}
        if self.pack_labels:
            self.primary = ui.select(
                options=self.pack_labels,
                value=next(iter(self.pack_labels)),
                label="Table set",
                on_change=self.choose_primary,
            ).classes("w-full")
            self.supplements = (
                ui.select(
                    options=self._supplement_options(self.primary.value),
                    value=[],
                    label="Supplements",
                    multiple=True,
                ).classes("w-full")
                if len(self.pack_labels) > 1
                else None
            )
        else:
            self.primary = None
            self.supplements = None
        self.character = ui.select(
            options={entry.id: f"{entry.label} — {entry.detail}" for entry in characters},
            value=characters[0].id if characters else None,
            label="Character",
        ).classes("w-full")
        self.premise = (
            ui.textarea(label="Premise", placeholder="What is this adventure about?")
            .classes("w-full")
            .props("autogrow")
        )
        self.scope = (
            ui.textarea(
                label="Scope",
                placeholder="How far does this go, and does it tend toward an ending?",
            )
            .classes("w-full")
            .props("autogrow")
        )
        self.style = ui.input(
            label="Art style", placeholder=f"Leave empty for: {engine.art_style}"
        ).classes("w-full")
        self.voice = ui.input(
            label="Narrator voice", placeholder="Leave empty for the default voice"
        ).classes("w-full")
        heading("Or upload the adventure")
        (
            ui.upload(on_upload=self.uploaded, max_files=1, auto_upload=True)
            .props(f'accept="{",".join(SOURCE_SUFFIXES)}"')
            .classes("w-full")
        )
        with ui.row().classes("w-full items-center").style("gap: 0.75rem"):
            self.button = ui.button(
                "Write the opening", icon="auto_stories", on_click=self.write
            ).props("color=primary")
            ui.label("Writing takes several minutes.").classes("text-xs opacity-60")
            if not characters:
                self.button.disable()
                ui.label("Make a character first.").classes("text-sm text-negative")

    async def write(self) -> None:
        title = (self.title.value or "").strip()
        premise = (self.premise.value or "").strip()
        scope = (self.scope.value or "").strip()
        character_id = self.character.value
        if not title or not scope or not (premise or self.document) or character_id is None:
            ui.notify("A title, a scope, a character, and a premise or a document.", type="warning")
            return
        if self.primary is not None and not self.primary.value:
            ui.notify("Choose a table set.", type="warning")
            return
        self.button.props("loading")
        meta = ScenarioMeta(
            title=title,
            premise=premise,
            scope=scope,
            art_style=(self.style.value or "").strip(),
            voice=(self.voice.value or "").strip(),
        )
        try:
            packs = None
            if self.primary is not None:
                chosen: list[str] = self.supplements.value if self.supplements is not None else []
                packs = parse(
                    PackSelection,
                    {
                        "primary": content_id(self.primary.value),
                        "supplements": tuple(content_id(pick) for pick in chosen),
                    },
                )
            character_id = content_id(character_id)
            name = await self.runtime.new_scenario(
                self.engine_id, meta, self.document, packs, character_id
            )
            opened = LaunchTarget(scenario_id=name, character_id=character_id)
        except Refusal as refused:
            ui.notify(str(refused), type="negative", multi_line=True)
            return
        finally:
            self.button.props(remove="loading")
        self._discard_uploads()
        LOGGER.info("scenario created: slug=%s", name)
        ui.navigate.to(game_path(opened))

    def _discard_uploads(self) -> None:
        # An abandoned page leaves one temp directory to the OS.
        if self.uploads is not None:
            shutil.rmtree(self.uploads, ignore_errors=True)
        self.uploads = None
        self.document = None


def character_page(runtime: Runtime) -> None:
    CharacterForm(runtime).build()


def scenario_page(runtime: Runtime) -> None:
    catalog = LauncherCatalog.read(runtime.library, runtime.store, runtime.engines)
    ScenarioForm(runtime, catalog).build()


def _engine_select(
    runtime: Runtime, chosen: EngineId, on_change: Callable[[ValueChangeEventArguments[str]], None]
) -> None:
    ui.select(
        options={engine.id: engine.title for engine in runtime.engines.values()},
        value=chosen,
        label="Rules",
        on_change=on_change,
    ).classes("w-full")


def _drop_stale(steps: tuple[CreationStep, ...], picks: dict[Slug, str]) -> None:
    """A new pack, or a skill moved onto its twin, can leave an answer its step no longer offers."""
    for step in steps:
        if step.options and picked(picks, step.id) not in {option.id for option in step.options}:
            picks.pop(step.id, None)
