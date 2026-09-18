import logging
import random
import shutil
from collections.abc import Callable, Generator
from contextlib import contextmanager
from functools import partial
from pathlib import Path
from tempfile import mkdtemp

from nicegui import ui
from nicegui.events import UploadEventArguments, ValueChangeEventArguments

from aidm.app.launch import LauncherCatalog, LaunchTarget
from aidm.app.runtime import Runtime
from aidm.core.creation import CreationStep, drop_stale, picked
from aidm.core.entities import EngineId, Refusal, Slug, content_id
from aidm.core.io import SOURCE_SUFFIXES
from aidm.core.model import ScenarioMeta
from aidm.core.play import DecisionOption
from aidm.ui import theme
from aidm.ui.widgets import (
    alert,
    game_path,
    heading,
    labeled_value,
    note,
    page_body,
    page_header,
    page_intro,
    warn,
)

LOGGER = logging.getLogger(__name__)


class DocumentUpload:
    """One uploaded source file, kept until the page is deleted."""

    def __init__(self) -> None:
        self.document: Path | None = None
        self.uploads: Path | None = None

    def build(self) -> None:
        ui.upload(on_upload=self.uploaded, max_files=1, auto_upload=True).props(
            f'accept="{",".join(SOURCE_SUFFIXES)}"'
        )
        # `on_disconnect` also fires on a reconnect, which would discard a live page's upload.
        ui.context.client.on_delete(self.discard)  # pyright: ignore[reportUnknownMemberType]

    async def uploaded(self, event: UploadEventArguments) -> None:
        # The source reader opens a path, and a PDF cannot be parsed from bytes.
        if self.uploads is None:
            self.uploads = Path(mkdtemp())
        if self.document is not None:
            self.document.unlink(missing_ok=True)
        path = self.uploads / Path(event.file.name).name
        await event.file.save(path)
        self.document = path
        note(f"Read {event.file.name}.")

    def discard(self) -> None:
        if self.uploads is not None:
            shutil.rmtree(self.uploads, ignore_errors=True)


class CharacterForm:
    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime
        self.engine_id = runtime.default_engine
        self.pack_id = runtime.default_pack
        self.picks: dict[Slug, str] = {}
        self.name: ui.input
        self.brief: ui.input
        self.ready: bool = False
        self.create_button: ui.button | None = None

    def build(self) -> None:
        with _form_page(
            self.runtime,
            self.engine_id,
            eyebrow="Character",
            title="New character",
            lead="Name them, pick their rules, and answer what the rules ask.",
        ):
            _engine_select(self.runtime, self.engine_id, self.choose_engine)
            self.name = ui.input(label="Name")
            self.brief = ui.input(label="Brief", placeholder="Who are they, in one sentence?")
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
        # The pack and the steps come from the engine, so an answer to the old ones means nothing.
        self.pack_id = self.runtime.default_pack
        self.picks.clear()
        self.steps.refresh()
        self.preview.refresh()

    def write(self, step_id: Slug, event: ValueChangeEventArguments[str | None]) -> None:
        self.picks[step_id] = (event.value or "").strip()

    def choose(self, step_id: Slug, event: ValueChangeEventArguments[str]) -> None:
        self.picks[step_id] = event.value
        self.answered()

    def choose_pack(self, event: ValueChangeEventArguments[str]) -> None:
        self.pack_id = content_id(event.value)
        self.answered()

    def answered(self) -> None:
        engine = self.runtime.engines[self.engine_id]
        drop_stale(engine.creation_steps(self.pack_id, self.picks), self.picks)
        self.steps.refresh()
        self.preview.refresh()

    def field(self, step: CreationStep) -> None:
        given = picked(self.picks, step.id)
        if not step.options:
            typed = ui.input(
                label=step.name,
                placeholder=step.hint or "In your own words",
                value=given,
                on_change=partial(self.write, step.id),
            )
            # Rebuilding the whole form on blur would destroy the field Tab just moved to.
            typed.on("blur", self.preview.refresh)
            return
        # Quasar returns typed text as its own key, so a typed answer only lands on a keyed label.
        options = {
            (option.name if step.allows_text else option.id): (
                f"{option.name} — {option.brief}" if option.brief else option.name
            )
            for option in step.options
        }
        chosen = ui.select(
            options=options,
            value=given or None,
            label=step.name,
            on_change=partial(self.choose, step.id),
            with_input=step.allows_text,
            new_value_mode="add-unique" if step.allows_text else None,
        )
        if step.hint:
            chosen.props(f'hint="{step.hint}"')

    def create(self) -> None:
        title = (self.name.value or "").strip()
        if not title:
            warn("Name the character.")
            return
        try:
            made = self.runtime.engines[self.engine_id].create_character(
                title, (self.brief.value or "").strip(), self.pack_id, self.picks
            )
            self.runtime.library.write_character(made)
        except Refusal as refused:
            alert(str(refused))
            return
        LOGGER.info("character created: slug=%s engine=%s", made.id, made.engine)
        ui.navigate.to("/")

    @ui.refreshable_method
    def steps(self) -> None:
        engine = self.runtime.engines[self.engine_id]
        _pack_select(engine.packs.options(), self.pack_id, self.choose_pack)
        for step in engine.creation_steps(self.pack_id, self.picks):
            self.field(step)

    @ui.refreshable_method
    def preview(self) -> None:
        engine = self.runtime.engines[self.engine_id]
        try:
            preview = engine.preview_character(
                engine.create_character(
                    (self.name.value or "").strip() or "Unnamed",
                    (self.brief.value or "").strip(),
                    self.pack_id,
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
        self.engine_id = runtime.default_engine
        self.pack_id = runtime.default_pack
        self.upload = DocumentUpload()
        self.title: ui.input
        self.seed_button: ui.button
        self.character: ui.select
        self.premise: ui.textarea
        self.scope: ui.textarea
        self.style: ui.input
        self.voice: ui.input
        self.button: ui.button

    def build(self) -> None:
        with _form_page(
            self.runtime,
            self.engine_id,
            eyebrow="Scenario",
            title="New scenario",
            lead="Describe the adventure, or upload one, and the worldsmith writes its opening.",
        ):
            _engine_select(self.runtime, self.engine_id, self.choose_engine)
            self.title = ui.input(label="Title")
            self.character_fields()
            self.premise = ui.textarea(label="Premise", placeholder="What is this adventure about?")
            self.scope = ui.textarea(
                label="Scope",
                placeholder="How far does this go, and does it tend toward an ending?",
            )
            self.style = ui.input(label="Art style")
            self._set_style_placeholder()
            self.voice = ui.input(
                label="Narrator voice", placeholder="Leave empty for the default voice"
            )
            heading("Or upload the adventure")
            self.upload.build()
            self.button_row()

    def choose_engine(self, event: ValueChangeEventArguments[str]) -> None:
        self.engine_id = EngineId(event.value)
        theme.set_look(self.runtime.engines[self.engine_id].look)
        self.pack_id = self.runtime.default_pack
        self.character_fields.refresh()
        self._set_style_placeholder()
        self.button_row.refresh()

    def _set_style_placeholder(self) -> None:
        engine = self.runtime.engines[self.engine_id]
        self.style.props(f'placeholder="Leave empty for: {engine.art_style}"')

    @ui.refreshable_method
    def character_fields(self) -> None:
        engine = self.runtime.engines[self.engine_id]
        characters = self.catalog.characters_for(self.engine_id)
        _pack_select(engine.packs.options(), self.pack_id, self.choose_pack)
        self.seed_button = ui.button("Roll a seed", icon="casino", on_click=self.roll_seed).props(
            "outline dense"
        )
        self.character = ui.select(
            options={entry.id: f"{entry.name} — {entry.brief}" for entry in characters},
            value=characters[0].id if characters else None,
            label="Character",
        )
        self.seed_button.set_visibility(bool(self.seeds()))

    def choose_pack(self, event: ValueChangeEventArguments[str]) -> None:
        self.pack_id = content_id(event.value)
        self.seed_button.set_visibility(bool(self.seeds()))

    def seeds(self) -> tuple[str, ...]:
        return self.runtime.engines[self.engine_id].packs.seeds(self.pack_id)

    def roll_seed(self) -> None:
        """A starting point the player edits; the seed is never stored on its own."""
        if seeds := self.seeds():
            self.premise.value = random.choice(seeds)  # the page's own die: it rolls no game die

    @ui.refreshable_method
    def button_row(self) -> None:
        characters = self.catalog.characters_for(self.engine_id)
        with ui.row().classes("w-full items-center game-gap-xl"):
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
        document = self.upload.document
        if not title or not scope or not (premise or document) or character_id is None:
            warn("A title, a scope, a character, and a premise or a document.")
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
            character_id = content_id(character_id)
            name = await self.runtime.new_scenario(
                self.engine_id, meta, document, self.pack_id, character_id
            )
            opened = LaunchTarget(scenario_id=name, character_id=character_id)
        except Refusal as refused:
            alert(str(refused))
            return
        finally:
            self.button.props(remove="loading")
        LOGGER.info("scenario created: slug=%s", name)
        ui.navigate.to(game_path(opened))


class PackForm:
    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime
        self.engine_id = runtime.default_engine
        self.upload = DocumentUpload()
        self.name: ui.input
        self.premise: ui.textarea
        self.license: ui.input
        self.button: ui.button

    def build(self) -> None:
        with _form_page(
            self.runtime,
            self.engine_id,
            eyebrow="Pack",
            title="New pack",
            lead="Name a genre, or upload a document, and the worldsmith writes the whole kit.",
        ):
            _engine_select(self.runtime, self.engine_id, self.choose_engine)
            self.name = ui.input(label="Name")
            self.premise = ui.textarea(
                label="Premise",
                placeholder="What genre is this, and what is a story in it about?",
            )
            heading("Or upload a document")
            self.upload.build()
            self.license = ui.input(
                label="Licence", placeholder="Optional: who wrote the source, under what terms"
            )
            with ui.row().classes("w-full items-center game-gap-xl"):
                self.button = ui.button(
                    "Write the pack", icon="auto_fix_high", on_click=self.write
                ).props("color=primary")
                ui.label("Writing takes several minutes.").classes("text-xs opacity-60")

    def choose_engine(self, event: ValueChangeEventArguments[str]) -> None:
        self.engine_id = EngineId(event.value)
        theme.set_look(self.runtime.engines[self.engine_id].look)

    async def write(self) -> None:
        name = (self.name.value or "").strip()
        premise = (self.premise.value or "").strip()
        document = self.upload.document
        if not name or not (premise or document):
            warn("A name, and a premise or a document.")
            return
        self.button.props("loading")
        try:
            pack_id = await self.runtime.new_pack(
                self.engine_id, name, premise, document, (self.license.value or "").strip()
            )
        except Refusal as refused:
            alert(str(refused))
            return
        finally:
            self.button.props(remove="loading")
        LOGGER.info("pack created: engine=%s slug=%s", self.engine_id, pack_id)
        note(f"Wrote {name}. Pick it on a character or a scenario.", good=True)
        ui.navigate.to("/")


def character_page(runtime: Runtime) -> None:
    CharacterForm(runtime).build()


def scenario_page(runtime: Runtime) -> None:
    catalog = LauncherCatalog.read(runtime.library, runtime.store, runtime.engines)
    ScenarioForm(runtime, catalog).build()


def new_pack_page(runtime: Runtime) -> None:
    PackForm(runtime).build()


@contextmanager
def _form_page(
    runtime: Runtime, engine_id: EngineId, *, eyebrow: str, title: str, lead: str
) -> Generator[None]:
    """The shape every create form wears: header, body, intro, one card."""
    page_header(title, look=runtime.engines[engine_id].look)
    with page_body():
        page_intro(eyebrow, title, lead)
        with ui.card().classes("w-full"):
            yield


def _engine_select(
    runtime: Runtime, chosen: EngineId, on_change: Callable[[ValueChangeEventArguments[str]], None]
) -> None:
    ui.select(
        options={engine.id: engine.title for engine in runtime.engines.values()},
        value=chosen,
        label="Rules",
        on_change=on_change,
    )


def _pack_select(
    offered: tuple[DecisionOption, ...],
    chosen: Slug,
    on_change: Callable[[ValueChangeEventArguments[str]], None],
) -> None:
    """The one pack choice; no select where the engine offers one pack alone."""
    if len(offered) == 1:
        return
    ui.select(
        options={option.id: option.name for option in offered},
        value=chosen,
        label="Pack",
        on_change=on_change,
    )
