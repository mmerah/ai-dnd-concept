import logging
import random
import shutil
from collections.abc import Callable, Generator, Iterable
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
        self.packs = runtime.engines[self.engine_id].select_packs(())
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
        # The packs and the steps come from the engine, so an answer to the old ones means nothing.
        self.packs = self.runtime.engines[self.engine_id].select_packs(())
        self.picks.clear()
        self.steps.refresh()
        self.preview.refresh()

    def write(self, step_id: Slug, event: ValueChangeEventArguments[str | None]) -> None:
        self.picks[step_id] = (event.value or "").strip()

    def choose(self, step_id: Slug, event: ValueChangeEventArguments[str]) -> None:
        self.picks[step_id] = event.value
        self.answered()

    def choose_packs(self, event: ValueChangeEventArguments[list[str]]) -> None:
        if (packs := _selected_packs(self.runtime, self.engine_id, event.value)) is not None:
            self.packs = packs
        self.answered()

    def answered(self) -> None:
        engine = self.runtime.engines[self.engine_id]
        drop_stale(engine.creation_steps(self.packs, self.picks), self.picks)
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
            typed.on("blur", self.preview.refresh)
            return
        # Quasar returns typed text as its own key, so a typed answer only lands on a keyed label.
        options = {
            (option.label if step.allows_text else option.id): (
                f"{option.label} — {option.detail}" if option.detail else option.label
            )
            for option in step.options
        }
        chosen = ui.select(
            options=options,
            value=given or None,
            label=step.label,
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
                title, (self.brief.value or "").strip(), self.packs, self.picks
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
        _packs_select(engine.supplement_options(), self.packs, self.choose_packs)
        for step in engine.creation_steps(self.packs, self.picks):
            self.field(step)

    @ui.refreshable_method
    def preview(self) -> None:
        engine = self.runtime.engines[self.engine_id]
        try:
            preview = engine.preview_character(
                engine.create_character(
                    (self.name.value or "").strip() or "Unnamed",
                    (self.brief.value or "").strip(),
                    self.packs,
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
        self.packs = runtime.engines[self.engine_id].select_packs(())
        self.upload = DocumentUpload()
        self.title: ui.input
        self.supplements: ui.select | None = None
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
        self.packs = self.runtime.engines[self.engine_id].select_packs(())
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
        self.supplements = _packs_select(engine.supplement_options(), self.packs, self.choose_packs)
        self.seed_button = ui.button("Roll a seed", icon="casino", on_click=self.roll_seed).props(
            "outline dense"
        )
        self.character = ui.select(
            options={entry.id: f"{entry.label} — {entry.detail}" for entry in characters},
            value=characters[0].id if characters else None,
            label="Character",
            on_change=lambda event: self.follow_character_id(event.value),
        )
        self.follow_character_id(self.character.value)
        self.follow_supplements()

    def follow_character_id(self, character_id: str | None) -> None:
        """The scenario plays what the character was made with, until the player says otherwise."""
        if self.supplements is None or character_id is None:
            return
        entry = next(
            entry
            for entry in self.catalog.characters_for(self.engine_id)
            if entry.id == character_id
        )
        # The SRD is implicit and never offered, so this keeps only the named supplements.
        self.supplements.value = self._offered(entry.packs)

    def choose_packs(self, event: ValueChangeEventArguments[list[str]]) -> None:
        if (packs := _selected_packs(self.runtime, self.engine_id, event.value)) is not None:
            self.packs = packs
        elif self.supplements is not None:
            self.supplements.value = self._offered(self.packs)
        self.follow_supplements()

    def _offered(self, packs: Iterable[Slug]) -> list[Slug]:
        """The named supplements among `packs`: what the select can show."""
        offered = {pack.id for pack in self.runtime.engines[self.engine_id].supplement_options()}
        return [pack for pack in packs if pack in offered]

    def seeds(self) -> tuple[str, ...]:
        return self.runtime.engines[self.engine_id].seeds(self.packs)

    def follow_supplements(self) -> None:
        self.seed_button.set_visibility(bool(self.seeds()))

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
                self.engine_id, meta, document, self.packs, character_id
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
        note(f"Wrote {name}. Pick it on a character and on a scenario.", good=True)
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


def _packs_select(
    offered: Iterable[DecisionOption],
    chosen: Iterable[Slug],
    on_change: Callable[[ValueChangeEventArguments[list[str]]], None],
) -> ui.select | None:
    """The one pack choice; `None` where the engine offers nothing beside its SRD."""
    options = {option.id: option.label for option in offered}
    if not options:
        return None
    return ui.select(
        options=options,
        value=[pack for pack in chosen if pack in options],
        label="Packs",
        multiple=True,
        on_change=on_change,
    )


def _selected_packs(
    runtime: Runtime, engine_id: EngineId, chosen: Iterable[str]
) -> tuple[Slug, ...] | None:
    """`None` where the choice is refused: the page says so and keeps the packs it had."""
    try:
        return runtime.engines[engine_id].select_packs(tuple(content_id(pick) for pick in chosen))
    except Refusal as refused:
        alert(str(refused))
        return None
