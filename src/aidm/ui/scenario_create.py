import logging
import tempfile
from pathlib import Path

from nicegui import ui
from nicegui.events import UploadEventArguments

from aidm.app.authoring.playability import FULL, OPENING
from aidm.app.authoring.session import AuthoringSession
from aidm.app.media import STYLE
from aidm.config import Settings
from aidm.content.sources import ExpansionPolicy
from aidm.state.base import content_id

from .busy import refuse_if_busy, working
from .panels import page_header

LOGGER = logging.getLogger(__name__)

_EXPANSION_LABELS: dict[ExpansionPolicy, str] = {
    "invented": "invented — the premise or document, expanded freely in play",
    "cited": "cited — written only from passages found in the document",
    "cited_or_invented": "cited_or_invented — the document, and the premise where it is silent",
    "closed": "closed — the authored world is all there is",
}
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
                expansion.set_value("cited")
                ui.notify(f"Using {event.file.name}")

            upload = (
                ui.upload(label="Source document", auto_upload=True, on_upload=uploaded)
                .classes("w-full")
                .props("outlined")
            )
            expansion = (
                ui.select(options=_EXPANSION_LABELS, label="How the world grows", value="invented")
                .classes("w-full")
                .props("outlined")
            )
            brief = (
                ui.select(options=_BRIEF_LABELS, label="How much to author", value="full")
                .classes("w-full")
                .props("outlined")
            )
            art_style = (
                ui.input(label="Art style", placeholder=STYLE).classes("w-full").props("outlined")
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
                        expansion=_policy(expansion.value),
                        art_style=(art_style.value or "").strip(),
                        document=document,
                        brief=FULL if brief.value == "full" else OPENING,
                    )
                except ValueError as error:
                    ui.notify(str(error), type="negative")
                    return
                session = new_session
                LOGGER.info(
                    "scenario authoring started: slug=%s expansion=%s document=%s",
                    session.slug,
                    session.expansion,
                    document is not None,
                )
                for widget in (slug, premise, upload, expansion, brief, art_style, author_button):
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
                    ui.code(session.draft.pretty(), language="json").classes("w-full")
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


def _policy(value: object) -> ExpansionPolicy:
    if not isinstance(value, str) or value not in _EXPANSION_LABELS:
        raise ValueError(f"{value!r} is not one of the expansion policies")
    return value
