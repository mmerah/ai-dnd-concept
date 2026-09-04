import logging
from collections.abc import Callable
from functools import partial
from pathlib import Path
from tempfile import mkdtemp

from nicegui import ui
from nicegui.events import UploadEventArguments, ValueChangeEventArguments

from aidm.app.launch import LauncherCatalog, LaunchTarget
from aidm.app.runtime import Runtime
from aidm.core.creation import CreationStep, picked
from aidm.core.entities import EngineId, Refusal, Slug
from aidm.core.io import SOURCE_SUFFIXES
from aidm.core.model import ScenarioKind, ScenarioMeta
from aidm.ui.widgets import game_path, labeled_value, page_header

LOGGER = logging.getLogger(__name__)


class CharacterForm:
    """The engine's creation steps, answered one at a time, previewed as the sheet they make."""

    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime
        self.engine_id = runtime.default_engine()
        self.picks: dict[Slug, str] = {}
        self.name: ui.input
        self.brief: ui.input

    def build(self) -> None:
        with page_header("New character"):
            pass
        with ui.column().classes("w-full q-pa-lg items-center"):
            with ui.card().classes("q-pa-lg").style("width: min(60rem, 100%)"):
                _engine_select(self.runtime, self.engine_id, self.choose_engine)
                self.name = ui.input(label="Name").classes("w-full").props("outlined")
                self.brief = (
                    ui.input(label="Brief", placeholder="Who are they, in one sentence?")
                    .classes("w-full")
                    .props("outlined")
                )
                self.form()

    def choose_engine(self, event: ValueChangeEventArguments[str]) -> None:
        self.engine_id = EngineId(event.value)
        # The steps come from the engine, so an answer to the old ones means nothing.
        self.picks.clear()
        self.form.refresh()

    def write(self, step_id: Slug, event: ValueChangeEventArguments[str | None]) -> None:
        self.picks[step_id] = (event.value or "").strip()

    def choose(self, step_id: Slug, event: ValueChangeEventArguments[str]) -> None:
        self.picks[step_id] = event.value
        _drop_stale(self.runtime.engines[self.engine_id].creation_steps(self.picks), self.picks)
        self.form.refresh()

    def field(self, step: CreationStep) -> None:
        given = picked(self.picks, step.id)
        if not step.options:
            typed = ui.input(
                label=step.prompt,
                placeholder=step.hint or "In your own words",
                value=given,
                on_change=partial(self.write, step.id),
            )
            # Refreshing per keystroke would take the focus away mid-word.
            typed.classes("w-full").props("outlined").on("blur", self.form.refresh)
            return
        chosen = ui.select(
            options={
                option.id: f"{option.label} — {option.detail}" if option.detail else option.label
                for option in step.options
            },
            value=given or None,
            label=step.prompt,
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
    def form(self) -> None:
        engine = self.runtime.engines[self.engine_id]
        for step in engine.creation_steps(self.picks):
            self.field(step)
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
            return
        ui.separator().classes("q-my-sm")
        for label, text in preview:
            labeled_value(label, text)
        ui.button("Create", icon="person_add", on_click=self.create).props("color=primary")


class ScenarioForm:
    """A premise or a document, one worldsmith call, and the game opens on the scene it wrote."""

    def __init__(self, runtime: Runtime, catalog: LauncherCatalog) -> None:
        self.runtime = runtime
        self.catalog = catalog
        self.engine_id = runtime.default_engine()
        self.document: Path | None = None
        self.title: ui.input
        self.packs: ui.select | None = None
        self.character: ui.select
        self.kind_toggle: ui.toggle
        self.premise: ui.textarea
        self.style: ui.input
        self.voice: ui.input
        self.button: ui.button

    def build(self) -> None:
        with page_header("New scenario"):
            pass
        with ui.column().classes("w-full q-pa-lg items-center"):
            with ui.card().classes("q-pa-lg").style("width: min(60rem, 100%)"):
                _engine_select(self.runtime, self.engine_id, self.choose_engine)
                self.form()

    async def took(self, event: UploadEventArguments) -> None:
        # The source reader opens a path, and a PDF cannot be parsed from bytes.
        path = Path(mkdtemp()) / Path(event.file.name).name
        await event.file.save(path)
        self.document = path
        ui.notify(f"Read {event.file.name}.")

    def choose_engine(self, event: ValueChangeEventArguments[str]) -> None:
        self.engine_id = EngineId(event.value)
        self.form.refresh()

    @ui.refreshable_method
    def form(self) -> None:
        engine = self.runtime.engines[self.engine_id]
        characters = self.catalog.characters_for(self.engine_id)
        self.title = ui.input(label="Title").classes("w-full").props("outlined")
        self.packs = (
            ui.select(
                options={pack.id: pack.label for pack in engine.pack_options()},
                value=[pack.id for pack in engine.pack_options()],
                label="Table sets",
                multiple=True,
            ).classes("w-full")
            if engine.pack_options()
            else None
        )
        self.character = ui.select(
            options={entry.id: f"{entry.title} — {entry.subtitle}" for entry in characters},
            value=characters[0].id if characters else None,
            label="Character",
        ).classes("w-full")
        self.kind_toggle = ui.toggle(
            {"one-shot": "One-shot", "campaign": "Campaign"}, value="one-shot"
        )
        ui.label(
            "A campaign opens at a home base with a board of jobs. "
            "Say where home is and who runs it."
        ).classes("text-sm opacity-70")
        self.premise = (
            ui.textarea(label="Premise", placeholder="What is this adventure about?")
            .classes("w-full")
            .props("outlined autogrow")
        )
        self.style = (
            ui.input(label="Art style", placeholder=f"Leave empty for: {engine.art_style}")
            .classes("w-full")
            .props("outlined")
        )
        self.voice = (
            ui.input(label="Narrator voice", placeholder="Leave empty for the default voice")
            .classes("w-full")
            .props("outlined")
        )
        ui.label("Or upload the adventure itself.").classes("text-sm opacity-70 q-mt-md")
        (
            ui.upload(on_upload=self.took, max_files=1, auto_upload=True)
            .props(f'accept="{",".join(SOURCE_SUFFIXES)}"')
            .classes("w-full")
        )
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
        character_id = self.character.value
        if not title or not (premise or self.document) or character_id is None:
            ui.notify("A title, a character, and a premise or a document.", type="warning")
            return
        self.button.props("loading")
        kind: ScenarioKind = "campaign" if self.kind_toggle.value == "campaign" else "one-shot"
        meta = ScenarioMeta(
            title=title,
            premise=premise,
            kind=kind,
            art_style=(self.style.value or "").strip(),
            voice=(self.voice.value or "").strip(),
        )
        try:
            name = await self.runtime.new_scenario(
                self.engine_id,
                meta,
                self.document,
                self.packs.value if self.packs is not None else (),
                character_id,
            )
            opened = LaunchTarget(scenario_id=name, character_id=character_id)
        except (OSError, Refusal) as refused:
            ui.notify(str(refused), type="negative", multi_line=True)
            return
        finally:
            self.button.props(remove="loading")
        LOGGER.info("scenario created: slug=%s", name)
        ui.navigate.to(game_path(opened))


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
