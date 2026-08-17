import logging
from collections.abc import Callable, Sequence
from pathlib import Path

from nicegui import ui
from nicegui.events import ValueChangeEventArguments

from aidm.app.session import Runtime
from aidm.content.authored import CreatedCharacter
from aidm.content.store import write_character
from aidm.state.base import EngineId, Slug, text_slug
from aidm.state.creation import AnyStep, CreationStep, TextStep, picked

from .panels import page_header

LOGGER = logging.getLogger(__name__)


def creation_page(runtime: Runtime, engine_id: EngineId) -> None:
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
                    # A pack switch keeps step ids but swaps their options, so a choice step's
                    # picks are pruned by surviving option, not only by surviving step. A text
                    # step has no options to prune against: its answers survive with its id.
                    offered = {
                        step.id: {option.id for option in step.options}
                        for step in steps
                        if isinstance(step, CreationStep)
                    }
                    written = {step.id: step.count for step in steps if isinstance(step, TextStep)}
                    for step_id in list(picks):
                        if (asked := written.get(step_id)) is not None:
                            # A pack can ask the same step for fewer answers; the surplus would
                            # otherwise sit in picks with no input left to clear it.
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
                    # Rebuilding drops what the player is part-way through answering, so the form
                    # is rebuilt only when an answer changed what a step asks or offers — and it
                    # goes first, so the preview reads the pruned picks.
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
    """Everything a rendered step puts on screen. What is *picked* is deliberately out: a step
    whose options are unmoved renders the same widget, and rebuilding it would take the cursor
    with it."""
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
        # Quasar's multi-select cannot hold the same value twice, so a repeatable step is one
        # select per pick.
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
