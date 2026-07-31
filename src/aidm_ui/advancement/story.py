from collections.abc import Callable

from nicegui import ui
from pydantic import BaseModel

from aidm_story.advancement import (
    AcquireGear,
    AddTag,
    IncreaseMaximumStress,
    RaiseApproach,
    RemoveBurden,
    RewriteBurden,
    StoryAdvancementPlan,
    StoryAdvancementPreview,
)
from aidm_story.models import APPROACH_NAMES, StoryApproach, StoryGearTag

from ..session_model import Session
from .flow import confirm_advancement


class StoryAdvancementUi:
    def render(self, session: Session, refresh: Callable[[], None]) -> None:
        status = session.app.advancement_status()
        ui.label(f"{session.app.state.player.name} — {status.headline}").classes(
            "text-sm font-bold"
        )
        ui.linear_progress(value=status.progress, show_value=False).classes("w-full")
        for line in status.detail:
            ui.label(line).classes("text-sm opacity-70")
        if not session.app.advancement_available():
            return
        try:
            preview = session.app.advancement_preview()
        except ValueError as error:
            ui.label(f"Cannot read the advancement: {error}").classes("text-negative text-sm")
            return
        if not isinstance(preview, StoryAdvancementPreview):
            raise TypeError(f"Story UI received advancement preview {type(preview).__name__}")
        ui.label("Choose one advancement").classes("text-h6 q-mt-md")
        with ui.column().classes("w-full").style("gap: 0.75rem"):
            self._raise_approach(session, refresh, preview)
            self._add_tag(session, refresh)
            self._burdens(session, refresh, preview)
            self._gear(session, refresh)
            if preview.max_stress < preview.max_stress_limit:
                with ui.card().classes("w-full"):
                    ui.label("Increase maximum stress").classes("font-bold")
                    ui.button(
                        "Review resilience increase",
                        on_click=lambda: self._review(session, refresh, IncreaseMaximumStress()),
                    ).props("color=primary")

    def _raise_approach(
        self,
        session: Session,
        refresh: Callable[[], None],
        preview: StoryAdvancementPreview,
    ) -> None:
        scores = {name: preview.approaches.score(name) for name in APPROACH_NAMES}
        options = {
            name: f"{name.capitalize()} ({score:+d} → {score + 1:+d})"
            for name, score in scores.items()
            if score < preview.approach_limit
        }
        if not options:
            return
        with ui.card().classes("w-full"):
            ui.label("Raise an approach").classes("font-bold")
            selected = ui.select(options=options, label="Approach").classes("w-full")
            ui.button(
                "Review approach increase",
                on_click=lambda: self._raise_selected(session, refresh, selected.value),
            ).props("color=primary")

    def _raise_selected(
        self,
        session: Session,
        refresh: Callable[[], None],
        value: object,
    ) -> None:
        if value not in APPROACH_NAMES:
            ui.notify("Choose an approach first.", type="warning")
            return
        approach: StoryApproach = value
        self._review(session, refresh, RaiseApproach(approach=approach))

    def _add_tag(self, session: Session, refresh: Callable[[], None]) -> None:
        with ui.card().classes("w-full"):
            ui.label("Add an edge or bond").classes("font-bold")
            tag_id = ui.input(label="Id (lowercase words joined by hyphens)").classes("w-full")
            name = ui.input(label="Name").classes("w-full")
            kind = ui.select(
                options={"edge": "Edge", "bond": "Bond"},
                label="Kind",
            ).classes("w-full")
            description = ui.input(label="Description").classes("w-full")
            ui.button(
                "Review new tag",
                on_click=lambda: self._review_tag(
                    session,
                    refresh,
                    tag_id.value,
                    name.value,
                    kind.value,
                    description.value,
                ),
            ).props("color=primary")

    def _review_tag(
        self,
        session: Session,
        refresh: Callable[[], None],
        tag_id: object,
        name: object,
        kind: object,
        description: object,
    ) -> None:
        tag_id_value = _text(tag_id)
        name_value = _text(name)
        description_value = _text(description)
        if tag_id_value is None or name_value is None or description_value is None:
            ui.notify("Complete the tag fields.", type="warning")
            return
        if kind not in ("edge", "bond"):
            ui.notify("Choose edge or bond.", type="warning")
            return
        self._review(
            session,
            refresh,
            AddTag(
                id=tag_id_value,
                name=name_value,
                kind=kind,
                description=description_value,
            ),
        )

    def _burdens(
        self,
        session: Session,
        refresh: Callable[[], None],
        preview: StoryAdvancementPreview,
    ) -> None:
        burdens = {tag.id: tag.name for tag in preview.tags if tag.kind == "burden"}
        if not burdens:
            return
        with ui.card().classes("w-full"):
            ui.label("Change a burden").classes("font-bold")
            selected = ui.select(options=burdens, label="Burden").classes("w-full")
            ui.button(
                "Review removing burden",
                on_click=lambda: self._remove_burden(session, refresh, selected.value),
            )
            name = ui.input(label="Rewritten name").classes("w-full")
            description = ui.input(label="Rewritten description").classes("w-full")
            ui.button(
                "Review rewritten burden",
                on_click=lambda: self._rewrite_burden(
                    session,
                    refresh,
                    selected.value,
                    name.value,
                    description.value,
                ),
            )

    def _remove_burden(
        self,
        session: Session,
        refresh: Callable[[], None],
        tag_id: object,
    ) -> None:
        if not isinstance(tag_id, str):
            ui.notify("Choose a burden first.", type="warning")
            return
        self._review(session, refresh, RemoveBurden(id=tag_id))

    def _rewrite_burden(
        self,
        session: Session,
        refresh: Callable[[], None],
        tag_id: object,
        name: object,
        description: object,
    ) -> None:
        tag_id_value = _text(tag_id)
        name_value = _text(name)
        description_value = _text(description)
        if tag_id_value is None or name_value is None or description_value is None:
            ui.notify("Choose and complete the burden.", type="warning")
            return
        self._review(
            session,
            refresh,
            RewriteBurden(
                id=tag_id_value,
                name=name_value,
                description=description_value,
            ),
        )

    def _gear(self, session: Session, refresh: Callable[[], None]) -> None:
        with ui.card().classes("w-full"):
            ui.label("Acquire Story gear").classes("font-bold")
            item_name = ui.input(label="Item name").classes("w-full")
            item_brief = ui.input(label="Item brief").classes("w-full")
            gear_name = ui.input(label="Gear benefit name").classes("w-full")
            gear_description = ui.input(label="Gear benefit description").classes("w-full")
            ui.button(
                "Review new gear",
                on_click=lambda: self._review_gear(
                    session,
                    refresh,
                    item_name.value,
                    item_brief.value,
                    gear_name.value,
                    gear_description.value,
                ),
            ).props("color=primary")

    def _review_gear(
        self,
        session: Session,
        refresh: Callable[[], None],
        item_name: object,
        item_brief: object,
        gear_name: object,
        gear_description: object,
    ) -> None:
        item_name_value = _text(item_name)
        item_brief_value = _text(item_brief)
        gear_name_value = _text(gear_name)
        gear_description_value = _text(gear_description)
        if (
            item_name_value is None
            or item_brief_value is None
            or gear_name_value is None
            or gear_description_value is None
        ):
            ui.notify("Complete every gear field.", type="warning")
            return
        self._review(
            session,
            refresh,
            AcquireGear(
                item_name=item_name_value,
                item_brief=item_brief_value,
                gear=StoryGearTag(
                    name=gear_name_value,
                    description=gear_description_value,
                ),
            ),
        )

    def _review(
        self,
        session: Session,
        refresh: Callable[[], None],
        decision: BaseModel,
    ) -> None:
        try:
            plan = session.app.advancement_plan(decision)
        except (TypeError, ValueError) as error:
            ui.notify(str(error), type="negative", multi_line=True)
            return
        if not isinstance(plan, StoryAdvancementPlan):
            raise TypeError(f"Story UI received plan {type(plan).__name__}")
        confirm_advancement(
            session,
            decision,
            refresh,
            title="Confirm Story advancement",
            confirm_label="Confirm advancement",
            body=lambda: self._summary(plan),
        )

    @staticmethod
    def _summary(plan: StoryAdvancementPlan) -> None:
        ui.label(plan.summary).classes("text-sm")


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
