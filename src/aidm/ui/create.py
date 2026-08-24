import logging
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

from nicegui import ui
from nicegui.events import UploadEventArguments, ValueChangeEventArguments

from aidm.app.authoring import FULL, OPENING, AuthoringSession
from aidm.app.launch import engine_ids
from aidm.app.runtime import Runtime
from aidm.config import Settings
from aidm.content.io import write_character
from aidm.content.model import CreatedCharacter
from aidm.state.creation import AnyStep, CreationStep, TextStep, picked
from aidm.state.entities import EngineId, Slug, content_id, text_slug

from .widgets import page_header, refuse_if_busy, working

LOGGER = logging.getLogger(__name__)


def character_page(runtime: Runtime, engine_id: EngineId) -> None:
    engine = runtime.engine(engine_id)
    with page_header("New character", engine.badge):
        pass
    creation = engine.creation
    with ui.column().classes("w-full q-pa-lg items-center"):
        if creation is None:
            with ui.card().style("width: min(48rem, 100%)").classes("q-pa-lg"):
                ui.label("These rules offer no character creation.").classes("text-negative")
            return
        picks: dict[Slug, tuple[str, ...]] = {}
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

                rendered: tuple[str, ...] = ()

                @ui.refreshable
                def form() -> None:
                    nonlocal rendered
                    steps = creation.steps(picks)
                    rendered = _shape(steps)
                    # Pack switches may preserve step ids while replacing their valid options.
                    offered = {
                        step.id: {option.id for option in step.options}
                        for step in steps
                        if isinstance(step, CreationStep)
                    }
                    written = {step.id: step.count for step in steps if isinstance(step, TextStep)}
                    for step_id in list(picks):
                        if (asked := written.get(step_id)) is not None:
                            # Drop surplus answers when a pack reduces a step's count.
                            picks[step_id] = picks[step_id][:asked]
                            continue
                        kept = tuple(
                            pick for pick in picks[step_id] if pick in offered.get(step_id, set())
                        )
                        if kept:
                            picks[step_id] = kept
                        else:
                            del picks[step_id]
                    for step in steps:
                        _step_widget(step, picks, refresh_form_and_preview)
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
                        chosen = _answer(step, picks)
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
                    # Rebuild only changed widgets to preserve unfinished input.
                    if _shape(creation.steps(picks)) != rendered:
                        form.refresh()
                    preview.refresh()

                form()
            with ui.card().classes("q-pa-lg").style("flex: 1; min-width: 0"):
                preview()


def _preview_lines(created: CreatedCharacter) -> list[tuple[str, str]]:
    """One (label, text) row per fact, engine-agnostic: the overlay is an opaque dict here."""
    lines = [(trait.name, trait.text) for trait in created.profile.traits]
    lines.extend(("carrying", item.name) for item in created.profile.items)
    for key, value in created.overlay.character.items():
        if isinstance(value, dict):
            if "current" in value and "maximum" in value:
                lines.append((key, f"{value['current']}/{value['maximum']}"))
            else:
                lines.extend((key, f"{inner}: {value[inner]}") for inner in value)
        elif isinstance(value, list):
            lines.extend((key, str(element)) for element in value)
        else:
            lines.append((key, str(value)))
    return lines


def _shape(steps: Sequence[AnyStep]) -> tuple[str, ...]:
    """Exclude picks so unchanged widgets retain focus while answers change."""
    parts: list[str] = []
    for step in steps:
        if isinstance(step, TextStep):
            parts.append(f"{step.id}: {step.prompt}: text: {step.hint}: {step.count}")
        else:
            parts.append(
                f"{step.id}: {step.prompt}: {step.choose}: {step.repeats}: "
                f"{[option.id for option in step.options]}"
            )
    return tuple(parts)


def _answer(step: AnyStep, picks: dict[Slug, tuple[str, ...]]) -> str:
    if isinstance(step, TextStep):
        return ", ".join(picked(picks, step.id))
    labels = {option.id: option.label for option in step.options}
    return ", ".join(labels.get(pick, pick) for pick in picked(picks, step.id))


def _step_widget(
    step: AnyStep, picks: dict[Slug, tuple[str, ...]], refresh: Callable[[], object]
) -> None:
    if isinstance(step, TextStep):
        _written_widget(step, picks, refresh)
    elif step.repeats:
        # Quasar multi-selects cannot hold duplicate values, so repeats use separate selects.
        _repeated_widget(step, picks, refresh)
    else:
        _chosen_widget(step, picks, refresh)


def _labels(step: CreationStep) -> dict[str, str]:
    return {
        option.id: f"{option.label} — {option.detail}" if option.detail else option.label
        for option in step.options
    }


def _chosen_widget(
    step: CreationStep,
    picks: dict[Slug, tuple[str, ...]],
    refresh: Callable[[], object],
) -> None:
    options = _labels(step)
    held = picked(picks, step.id)
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


def _repeated_widget(
    step: CreationStep,
    picks: dict[Slug, tuple[str, ...]],
    refresh: Callable[[], object],
) -> None:
    options = _labels(step)
    held = picked(picks, step.id)
    for index in range(step.choose):
        value = held[index] if index < len(held) else None
        label = step.prompt if step.choose == 1 else f"{step.prompt} {index + 1}"

        def changed(event: ValueChangeEventArguments[object], index: int = index) -> None:
            chosen = event.value if isinstance(event.value, str) else ""
            _write_answer(picks, step.id, step.choose, index, chosen)
            refresh()

        ui.select(options=options, value=value, label=label, on_change=changed).classes("w-full")


def _written_widget(
    step: TextStep,
    picks: dict[Slug, tuple[str, ...]],
    refresh: Callable[[], object],
) -> None:
    held = picked(picks, step.id)
    for index in range(step.count):
        value = held[index] if index < len(held) else ""
        label = step.prompt if step.count == 1 else f"{step.prompt} {index + 1}"

        def changed(event: ValueChangeEventArguments[object], index: int = index) -> None:
            text = event.value.strip() if isinstance(event.value, str) else ""
            _write_answer(picks, step.id, step.count, index, text)
            refresh()

        ui.input(
            label=label,
            value=value,
            placeholder=step.hint,
            on_change=changed,  # pyright: ignore[reportArgumentType]
        ).classes("w-full").props("outlined")


def _write_answer(
    picks: dict[Slug, tuple[str, ...]], step_id: Slug, length: int, index: int, value: str
) -> None:
    answers = list(picked(picks, step_id)[:length])
    answers += [""] * (length - len(answers))
    answers[index] = value
    if any(answer.strip() for answer in answers):
        picks[step_id] = tuple(answers)
    else:
        picks.pop(step_id, None)


def _taken(directory: Path) -> tuple[str, ...]:
    if not directory.is_dir():
        return ()
    return tuple(path.name for path in directory.iterdir() if path.is_dir())


_BRIEF_LABELS = {"full": "a whole scenario", "opening": "an opening slice, grown in play"}


def scenario_page(config: Settings) -> None:
    with page_header("New scenario"):
        pass
    document: Path | None = None
    session: AuthoringSession | None = None
    exchanges: list[tuple[str, str]] = []

    with ui.row().classes("no-wrap items-start").style("width: min(80rem, 100%); gap: 1rem"):
        with ui.card().classes("q-pa-lg").style("flex: 1; min-width: 0"):
            slug = (
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
            engines = (
                ui.select(
                    options=list(engine_ids()),
                    value=list(engine_ids()),
                    multiple=True,
                    label="Rules it plays under",
                )
                .classes("w-full")
                .props("outlined")
            )
            brief = (
                ui.select(options=_BRIEF_LABELS, label="How much to author", value="full")
                .classes("w-full")
                .props("outlined")
            )
            art_style = (
                ui.input(label="Art style", placeholder=config.media.style)
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
                    new_session = AuthoringSession(
                        slug=content_id(slug.value or ""),
                        premise=(premise.value or "").strip(),
                        config=config,
                        grows=bool(grows.value),
                        engines=_engines(engines.value),
                        art_style=(art_style.value or "").strip(),
                        document=document,
                        brief=FULL if brief.value == "full" else OPENING,
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
                    slug,
                    premise,
                    upload,
                    grows,
                    engines,
                    brief,
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
                    summary = await session.write()
                    LOGGER.info("scenario written: slug=%s", session.slug)
                    ui.notify(summary, type="positive", multi_line=True)
                    ui.navigate.to("/")
                status.refresh()

            readback()


def _engines(value: object) -> tuple[EngineId, ...]:
    chosen = (
        tuple(engine for engine in engine_ids() if engine in value)
        if isinstance(value, list)
        else ()
    )
    if not chosen:
        raise ValueError("choose at least one ruleset")
    return chosen
