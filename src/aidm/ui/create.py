import logging
import tempfile
from functools import partial
from pathlib import Path
from typing import cast

from nicegui import ui
from nicegui.events import UploadEventArguments, ValueChangeEventArguments

from aidm.app.runtime import Runtime
from aidm.authoring.run import ScenarioRun, scenario_run
from aidm.content.io import write_character
from aidm.harness.driver import Driver
from aidm.state.creation import picked
from aidm.state.entities import EngineId, Slug, content_id

from .widgets import decision_widget, labeled_value, page_header, refuse_if_busy, working

LOGGER = logging.getLogger(__name__)


def character_page(runtime: Runtime, engine_id: str) -> None:
    engine = runtime.engines.get(EngineId(engine_id))
    if engine is None:
        raise ValueError(f"unknown engine {engine_id!r}")
    with page_header("New character", engine.badge):
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
                    created = creation.create(title, (brief.value or "").strip(), picks)
                    write_character(runtime.settings.characters_dir, engine.id, created)
                except ValueError as refused:
                    ui.notify(str(refused), type="negative")
                    return
                LOGGER.info("character created: slug=%s engine=%s", created.id, engine.id)
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
                    preview = creation.create(
                        (name.value or "").strip() or "Unnamed",
                        (brief.value or "").strip(),
                        picks,
                    )
                except ValueError as refused:
                    ui.label(f"Not ready yet: {refused}").classes("text-sm opacity-50")
                    return
                ui.separator().classes("q-my-sm")
                rows = [(trait.name, trait.text) for trait in preview.profile.traits]
                rows.extend(("carrying", item.name) for item in preview.profile.items)
                for item in preview.profile.items:
                    item_rules = preview.item_rules.get(item.id, {})
                    item_rows = engine.rules_types["item"].model_validate(item_rules).rows()
                    rows.extend(
                        (f"{item.name}: {label}", value) for label, value in item_rows if value
                    )
                rows.extend(engine.rules_types["actor"].model_validate(preview.rules).rows())
                for label, text in rows:
                    labeled_value(label, text)
                ui.button("Create", icon="person_add", on_click=create).props("color=primary")

            form()


def _engine_and_packs(runtime: Runtime) -> tuple[ui.select, ui.select]:
    engine = (
        ui.select(
            options=list(runtime.engines),
            value=next(iter(runtime.engines)),
            label="Rules it plays under",
        )
        .classes("w-full")
        .props("outlined")
    )
    packs = (
        ui.select(
            options=list(_engine(runtime, engine.value).packs),
            value=["srd"],
            label="Content packs",
            multiple=True,
        )
        .classes("w-full")
        .props("outlined")
    )

    def changed_engine(event: ValueChangeEventArguments[object]) -> None:
        packs.options = list(_engine(runtime, event.value).packs)
        packs.value = ["srd"]
        packs.update()

    engine.on_value_change(changed_engine)
    return engine, packs


def scenario_page(runtime: Runtime) -> None:
    settings = runtime.settings
    with page_header("New scenario"):
        pass
    document: Path | None = None
    session: ScenarioRun | None = None
    exchanges: list[tuple[str, str]] = []

    with ui.row().classes("no-wrap items-start").style("width: min(80rem, 100%); gap: 1rem"):
        with ui.card().classes("q-pa-lg").style("flex: 1; min-width: 0"):
            scenario_id = (
                ui.input(label="Slug", placeholder="the-drowned-road")
                .classes("w-full")
                .props("outlined")
            )
            premise = (
                ui.textarea(label="Premise", placeholder="What is this adventure about?")
                .classes("w-full")
                .props("outlined autogrow")
            )

            async def uploaded(event: UploadEventArguments) -> None:
                nonlocal document
                target = Path(tempfile.mkdtemp()) / event.file.name
                await event.file.save(target)
                document = target
                ui.notify(f"Using {event.file.name}")

            upload = (
                ui.upload(label="Source document", auto_upload=True, on_upload=uploaded)
                .classes("w-full")
                .props("outlined")
            )
            grows = ui.switch("Grows during play", value=True).classes("w-full")
            engine, packs = _engine_and_packs(runtime)
            art_style = (
                ui.input(label="Art style", placeholder=settings.media.style)
                .classes("w-full")
                .props("outlined")
            )
            author_button = (
                ui.button("Author", icon="auto_stories", on_click=lambda: start())
                .props("color=primary")
                .classes("q-mt-md")
            )

            @ui.refreshable
            def status() -> None:
                if session is not None and session.busy:
                    with ui.row().classes("items-center").style("gap: 0.5rem"):
                        ui.spinner()
                        ui.label("Authoring — this takes a few minutes.").classes("text-sm")

            async def start() -> None:
                nonlocal session
                if session is not None:
                    return
                try:
                    new_session = scenario_run(
                        settings,
                        _engine(runtime, engine.value),
                        content_id(scenario_id.value or ""),
                        (premise.value or "").strip(),
                        bool(grows.value),
                        document,
                        packs=_packs(packs.value),
                        art_style=(art_style.value or "").strip(),
                    )
                except ValueError as error:
                    ui.notify(str(error), type="negative")
                    return
                session = new_session
                LOGGER.info(
                    "scenario authoring started: slug=%s grows=%s document=%s",
                    session.slug,
                    session.grows,
                    document is not None,
                )
                for widget in (
                    scenario_id,
                    premise,
                    upload,
                    grows,
                    engine,
                    packs,
                    art_style,
                    author_button,
                ):
                    widget.disable()
                readback.refresh()
                async with working(session):
                    status.refresh()
                    summary = await session.send(session.opening_prompt)
                    exchanges.append((session.premise or "the source document", summary))
                status.refresh()
                readback.refresh()
                chat_box.refresh()

            status()

            @ui.refreshable
            def chat_box() -> None:
                if session is None:
                    return
                for instruction, summary in exchanges:
                    ui.chat_message(instruction, sent=True)
                    ui.chat_message(summary, sent=False)
                with ui.row().classes("w-full no-wrap").style("gap: 0.5rem"):
                    box = (
                        ui.input(placeholder="What should change?")
                        .classes("flex-grow")
                        .props("outlined")
                    )
                    ui.button(icon="send", on_click=lambda: send(box)).props("round")

            async def send(box: ui.input) -> None:
                if session is None or refuse_if_busy(session):
                    return
                instruction = (box.value or "").strip()
                if not instruction:
                    return
                box.value = ""
                async with working(session):
                    status.refresh()
                    exchanges.append((instruction, await session.send(instruction)))
                status.refresh()
                readback.refresh()
                chat_box.refresh()

            chat_box()

        with ui.card().classes("q-pa-lg").style("flex: 1; min-width: 0"):

            @ui.refreshable
            def readback() -> None:
                if session is None:
                    ui.label("Fill in the form and start authoring.").classes("text-sm opacity-70")
                    return
                refusal = session.refusal()
                if refusal is None:
                    ui.label("Plays.").classes("text-positive text-sm")
                else:
                    ui.label(refusal).classes("text-negative text-sm")
                with ui.scroll_area().classes("w-full").style("height: calc(100vh - 22rem)"):
                    readable = session.draft.as_json()
                    ui.code(readable, language="json").classes("w-full")
                ui.button("Save scenario", icon="save", on_click=save).props(
                    "color=primary"
                ).classes("q-mt-md")

            async def save() -> None:
                if session is None or refuse_if_busy(session):
                    return
                async with working(session):
                    status.refresh()
                    summary = session.write()
                    LOGGER.info("scenario written: slug=%s", session.slug)
                    ui.notify(summary, type="positive", multi_line=True)
                    ui.navigate.to("/")
                status.refresh()

            readback()


def agent_scenario_page(driver: Driver, runtime: Runtime) -> None:
    """Code mode has no api_key for the authoring roles, so the agent writes the scenario."""
    with page_header("New scenario"):
        pass
    document: Path | None = None

    with ui.card().classes("q-pa-lg").style("width: min(60rem, 100%)"):
        scenario_id = (
            ui.input(label="Slug", placeholder="the-drowned-road")
            .classes("w-full")
            .props("outlined")
        )
        premise = (
            ui.textarea(label="Premise", placeholder="What is this adventure about?")
            .classes("w-full")
            .props("outlined autogrow")
        )
        engine, packs = _engine_and_packs(runtime)
        grows = ui.switch("Grows during play", value=True).classes("w-full")

        async def uploaded(event: UploadEventArguments) -> None:
            nonlocal document
            target = Path(tempfile.mkdtemp()) / event.file.name
            await event.file.save(target)
            document = target
            ui.notify(f"Using {event.file.name}")

        ui.upload(label="Source document", auto_upload=True, on_upload=uploaded).classes(
            "w-full"
        ).props("outlined")

        async def write() -> None:
            try:
                chosen = _engine(runtime, engine.value).id
                chosen_packs = _packs(packs.value)
                slug_value = content_id((scenario_id.value or "").strip())
            except ValueError as error:
                ui.notify(str(error), type="negative")
                return
            # `source` is a path the tool opens, so it is named only when a document was uploaded.
            source = "" if document is None else f" source={document}."
            instruction = (
                f"Write a scenario with slug {slug_value!r}, "
                f"premise: {(premise.value or '').strip()}. "
                f"It must play under {chosen!r} with packs={chosen_packs!r}. "
                f"grows={bool(grows.value)}.{source} "
                "Call begin_scenario with exactly those values, then run the authoring loop and "
                "finish_scenario."
            )
            write_button.disable()
            LOGGER.info("agent authoring started: slug=%s document=%s", slug_value, document)
            try:
                async for line in driver.play(instruction):
                    log.push(line)
                ui.notify("Scenario written.", type="positive")
            except Exception as error:
                ui.notify(f"{type(error).__name__}: {error}", type="negative", multi_line=True)
            finally:
                write_button.enable()

        write_button = (
            ui.button("Write it", icon="auto_stories", on_click=write)
            .props("color=primary")
            .classes("q-mt-md")
        )
        log = ui.log(max_lines=500).classes("w-full h-96 text-xs")


def _engine(runtime: Runtime, value: object):
    """No return annotation: `ui` may not import `aidm.engines`, even to name the type."""
    chosen = runtime.engines.get(EngineId(str(value)))
    if chosen is None:
        raise ValueError("choose a ruleset")
    return chosen


def _packs(value: object) -> tuple[Slug, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in cast(list[object], value) if isinstance(item, str))
